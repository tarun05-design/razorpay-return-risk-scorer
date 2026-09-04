"""
labeling.py
-----------
Olist's public dataset has NO explicit "returned" flag. Building a return-risk
scorer on this data requires an honest, DOCUMENTED proxy label, plus evidence
that the proxy actually tracks return-like behaviour rather than noise.

Label definition
=================
POSITIVE (return-risk = 1):
    - order_status == 'canceled'                       (order never fulfilled)
    - OR delivered order with review_score in {1, 2}    (strong dissatisfaction)

NEGATIVE (return-risk = 0):
    - delivered order with review_score in {4, 5}       (satisfied)

DROPPED (label too ambiguous to trust):
    - review_score == 3 (neutral — could go either way)
    - delivered orders with no review at all
    - non-terminal statuses at data-snapshot time (shipped, processing,
      invoiced, approved, created, unavailable) — outcome not yet known

Validation of the proxy
========================
We check whether review_score<=2 orders actually talk about returns/refunds/
cancellations far more than review_score>=4 orders, using a Portuguese keyword
search over free-text review comments. This is NOT used as a model feature
(it's computed after delivery, so it would leak) — it exists purely to justify
the label choice, and the enrichment ratio is reported in the metrics output
so judges can audit it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

RETURN_KEYWORDS = re.compile(
    r"devolv|troca|reembols|estorn|cancel|n[aã]o\s+recebi|produto\s+errado|veio\s+errado",
    flags=re.IGNORECASE,
)


@dataclass
class LabelValidation:
    low_score_n: int
    low_score_keyword_hits: int
    high_score_n: int
    high_score_keyword_hits: int

    @property
    def low_score_rate(self) -> float:
        return self.low_score_keyword_hits / self.low_score_n if self.low_score_n else 0.0

    @property
    def high_score_rate(self) -> float:
        return self.high_score_keyword_hits / self.high_score_n if self.high_score_n else 0.0

    @property
    def enrichment(self) -> float:
        return self.low_score_rate / self.high_score_rate if self.high_score_rate else float("inf")

    def as_dict(self) -> dict:
        return {
            "low_score_n": self.low_score_n,
            "low_score_keyword_hits": self.low_score_keyword_hits,
            "low_score_keyword_rate": round(self.low_score_rate, 4),
            "high_score_n": self.high_score_n,
            "high_score_keyword_hits": self.high_score_keyword_hits,
            "high_score_keyword_rate": round(self.high_score_rate, 4),
            "enrichment_ratio": round(self.enrichment, 2),
        }


def validate_proxy_label(reviews: pd.DataFrame) -> LabelValidation:
    """Quantify how much more often low-score reviews mention returns/refunds
    than high-score reviews. This is the evidence for the label design."""
    text = reviews["review_comment_message"].fillna("")
    has_kw = text.str.contains(RETURN_KEYWORDS, regex=True)

    low = reviews["review_score"].isin([1, 2])
    high = reviews["review_score"].isin([4, 5])

    return LabelValidation(
        low_score_n=int(low.sum()),
        low_score_keyword_hits=int((low & has_kw).sum()),
        high_score_n=int(high.sum()),
        high_score_keyword_hits=int((high & has_kw).sum()),
    )


def build_labels(orders: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame indexed by order_id with columns:
        return_risk : 0/1  (only for rows kept)
        label_source: 'canceled' | 'low_review' | 'high_review' (audit trail)
    Ambiguous rows are simply absent from the result.
    """
    # one review score per order (an order can have >1 review; take the first
    # chronologically, which is standard practice for this dataset)
    rev = (
        reviews.sort_values("review_creation_date")
        .drop_duplicates("order_id", keep="first")[["order_id", "review_score"]]
    )

    df = orders[["order_id", "order_status"]].merge(rev, on="order_id", how="left")

    is_canceled = df["order_status"] == "canceled"
    is_delivered = df["order_status"] == "delivered"
    is_low = df["review_score"].isin([1, 2])
    is_high = df["review_score"].isin([4, 5])

    positive = is_canceled | (is_delivered & is_low)
    negative = is_delivered & is_high
    keep = positive | negative

    out = df.loc[keep, ["order_id"]].copy()
    out["return_risk"] = positive.loc[keep].astype(int)

    source = pd.Series(index=df.index, dtype=object)
    source[is_canceled] = "canceled"
    source[is_delivered & is_low] = "low_review"
    source[is_delivered & is_high] = "high_review"
    out["label_source"] = source.loc[keep].values

    return out.reset_index(drop=True)
