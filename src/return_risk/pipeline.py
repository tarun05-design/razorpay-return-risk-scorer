"""
pipeline.py
-----------
Wires together: raw CSV loading -> label construction -> feature engineering
-> a TIME-BASED train/test split.

Why a time-based split and not a random split?
A return-risk scorer is deployed forward in time: it scores orders that
haven't happened yet, using patterns learned from past orders. A random
80/20 split would let the model "see the future" through the expanding
seller-prior feature and through category/seasonal drift, and would report
an optimistic, dishonest number. Splitting by purchase date (last ~20% of
orders chronologically = test set) mimics how the model would actually be
evaluated in production.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .features import add_expanding_seller_prior, build_order_level_table
from .labeling import build_labels, validate_proxy_label

FEATURE_COLUMNS_NUMERIC = [
    "n_items", "n_distinct_products", "n_distinct_sellers",
    "total_price", "total_freight", "avg_price", "max_price",
    "avg_weight_g", "avg_photos_qty", "avg_desc_length", "avg_name_length",
    "n_payment_installments", "total_payment_value", "n_payment_methods",
    "promised_delivery_days", "purchase_dow", "purchase_hour", "purchase_month",
    "is_interstate", "freight_to_price_ratio", "price_per_item",
    "is_multi_item", "is_multi_seller", "high_installments",
    "seller_prior_bad_rate", "seller_prior_n_orders",
]
FEATURE_COLUMNS_CATEGORICAL = [
    "product_category_name_english", "payment_type", "customer_state", "seller_state",
]
ALL_FEATURE_COLUMNS = FEATURE_COLUMNS_NUMERIC + FEATURE_COLUMNS_CATEGORICAL


def load_raw(data_dir: Path) -> dict[str, pd.DataFrame]:
    def rd(name: str) -> pd.DataFrame:
        return pd.read_csv(data_dir / name)

    return {
        "orders": rd("olist_orders_dataset.csv"),
        "items": rd("olist_order_items_dataset.csv"),
        "payments": rd("olist_order_payments_dataset.csv"),
        "reviews": rd("olist_order_reviews_dataset.csv"),
        "products": rd("olist_products_dataset.csv"),
        "sellers": rd("olist_sellers_dataset.csv"),
        "customers": rd("olist_customers_dataset.csv"),
        "category_translation": rd("product_category_name_translation.csv"),
    }


def build_dataset(data_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Returns (modeling_df, audit_info). modeling_df has one row per LABELED
    order with all features + the label. audit_info carries the proxy-label
    validation stats for the report."""
    raw = load_raw(data_dir)

    labels = build_labels(raw["orders"], raw["reviews"])
    validation = validate_proxy_label(raw["reviews"])

    order_table = build_order_level_table(
        orders=raw["orders"],
        items=raw["items"],
        payments=raw["payments"],
        products=raw["products"],
        sellers=raw["sellers"],
        customers=raw["customers"],
        category_translation=raw["category_translation"],
    )

    global_base_rate = labels["return_risk"].mean()
    order_table = add_expanding_seller_prior(order_table, labels, global_base_rate)

    df = order_table.merge(labels, on="order_id", how="inner")
    df = df.sort_values("order_purchase_timestamp").reset_index(drop=True)

    for c in FEATURE_COLUMNS_CATEGORICAL:
        df[c] = df[c].fillna("unknown").astype("category")

    audit_info = {
        "n_labeled_orders": int(len(df)),
        "base_rate_return_risk": round(float(global_base_rate), 4),
        "label_source_counts": df["label_source"].value_counts().to_dict(),
        "proxy_label_validation": validation.as_dict(),
    }
    return df, audit_info


def time_based_split(df: pd.DataFrame, test_frac: float = 0.2):
    n = len(df)
    cut = int(n * (1 - test_frac))
    cutoff_date = df.iloc[cut]["order_purchase_timestamp"]
    train = df.iloc[:cut].copy()
    test = df.iloc[cut:].copy()
    return train, test, cutoff_date
