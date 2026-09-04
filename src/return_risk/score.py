"""
score.py
--------
The "verifier" surface: takes one order's raw, pre-outcome fields (exactly
what a merchant's checkout/OMS would know at order time) and returns a
calibrated return-risk score, a flag decision at a given threshold, and
plain-language reason codes — not just a number with no audit trail.

This is deliberately NOT an LLM call. It's a deterministic function of a
persisted model + a persisted seller-stats snapshot, so a merchant gets a
sub-millisecond, reproducible, auditable score.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .action_policy import PolicyAction, evaluate_action_policy
from .pipeline import ALL_FEATURE_COLUMNS, FEATURE_COLUMNS_CATEGORICAL
from .seller_store import SellerPriorLookup


@dataclass
class RiskResult:
    risk_score: float
    flagged: bool
    threshold_used: float
    reason_codes: list[str] = field(default_factory=list)
    action: Optional[PolicyAction] = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "risk_score": round(self.risk_score, 4),
            "flagged": self.flagged,
            "threshold_used": self.threshold_used,
            "reason_codes": self.reason_codes,
        }
        if self.action is not None:
            data["action"] = self.action.as_dict()
        return data


REQUIRED_ORDER_FIELDS = [
    "order_purchase_timestamp", "order_estimated_delivery_date",
    "customer_state", "seller_id", "seller_state",
    "product_category_name_english", "payment_type",
    "n_items", "n_distinct_products", "n_distinct_sellers",
    "total_price", "total_freight", "avg_price", "max_price",
    "avg_weight_g", "avg_photos_qty", "avg_desc_length", "avg_name_length",
    "n_payment_installments", "total_payment_value", "n_payment_methods",
]


def _derive_row(order: dict, seller_prior_bad_rate: float, seller_prior_n_orders: int) -> dict:
    purchase = pd.Timestamp(order["order_purchase_timestamp"])
    estimated = pd.Timestamp(order["order_estimated_delivery_date"])

    row = dict(order)
    row["promised_delivery_days"] = (estimated - purchase).days
    row["purchase_dow"] = purchase.dayofweek
    row["purchase_hour"] = purchase.hour
    row["purchase_month"] = purchase.month
    row["is_interstate"] = int(order["customer_state"] != order["seller_state"])
    row["freight_to_price_ratio"] = (
        order["total_freight"] / order["total_price"] if order["total_price"] else None
    )
    row["price_per_item"] = order["total_price"] / order["n_items"] if order["n_items"] else None
    row["is_multi_item"] = int(order["n_items"] > 1)
    row["is_multi_seller"] = int(order["n_distinct_sellers"] > 1)
    row["high_installments"] = int(order.get("n_payment_installments", 0) >= 6)
    row["seller_prior_bad_rate"] = seller_prior_bad_rate
    row["seller_prior_n_orders"] = seller_prior_n_orders
    return row


def _reason_codes(row: dict, reference_stats: dict) -> list[str]:
    """Lightweight, transparent explanation layer: flag features that are
    unusual relative to the training population, in order of known global
    importance. Not SHAP — deliberately simple enough to read in one pass."""
    reasons = []

    spb = row["seller_prior_bad_rate"]
    if row["seller_prior_n_orders"] >= 5 and spb > reference_stats["seller_prior_bad_rate_p75"]:
        reasons.append(f"Seller's historical bad-order rate ({spb:.1%}) is in the top quartile of sellers")
    elif row["seller_prior_n_orders"] < 5:
        reasons.append("New/thin-history seller — scored using platform base rate, less certainty")

    if row["n_items"] >= reference_stats["n_items_p90"]:
        reasons.append(f"Unusually large order ({row['n_items']} items)")

    if row["n_distinct_sellers"] > 1:
        reasons.append(f"Order splits across {row['n_distinct_sellers']} sellers (split-shipment risk)")

    if row["promised_delivery_days"] >= reference_stats["promised_delivery_days_p90"]:
        reasons.append(f"Long promised delivery window ({row['promised_delivery_days']} days)")

    if row.get("freight_to_price_ratio") and row["freight_to_price_ratio"] > reference_stats["freight_ratio_p90"]:
        reasons.append("Freight cost is unusually high relative to order value")

    if not reasons:
        reasons.append("No individually unusual factors — risk driven by combination of features")

    return reasons


class ReturnRiskScorer:
    def __init__(self, model_path: Path, seller_store_path: Path, reference_stats_path: Path):
        import joblib
        self.model = joblib.load(model_path)
        self.seller_lookup = SellerPriorLookup(seller_store_path)
        with open(reference_stats_path) as f:
            self.reference_stats = json.load(f)

    def score(self, order: dict, threshold: float = 0.598) -> RiskResult:
        missing = [f for f in REQUIRED_ORDER_FIELDS if f not in order]
        if missing:
            raise ValueError(f"Missing required order fields: {missing}")

        spb, spn = self.seller_lookup.lookup(order["seller_id"])
        row = _derive_row(order, spb, spn)

        X = pd.DataFrame([row])[ALL_FEATURE_COLUMNS]
        for c in FEATURE_COLUMNS_CATEGORICAL:
            X[c] = X[c].fillna("unknown").astype("category")

        prob = float(self.model.predict_proba(X)[:, 1][0])
        flagged = prob >= threshold
        reasons = _reason_codes(row, self.reference_stats)
        action = evaluate_action_policy(
            risk_score=prob,
            total_price=float(order.get("total_price", 100.0)),
            total_freight=float(order.get("total_freight", 20.0)),
            cost_optimal_threshold=threshold,
        )

        return RiskResult(
            risk_score=prob,
            flagged=flagged,
            threshold_used=threshold,
            reason_codes=reasons,
            action=action,
        )
