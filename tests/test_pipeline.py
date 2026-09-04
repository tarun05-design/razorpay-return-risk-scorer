"""
Tests focus on the two things most likely to silently break trust in this
project: (1) the label logic doing what it claims, and (2) the seller-prior
feature not leaking future information into the past.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from return_risk.labeling import build_labels, validate_proxy_label  # noqa: E402
from return_risk.features import add_expanding_seller_prior  # noqa: E402


def test_build_labels_canceled_is_positive():
    orders = pd.DataFrame({
        "order_id": ["o1"], "order_status": ["canceled"],
    })
    reviews = pd.DataFrame(columns=["order_id", "review_score", "review_creation_date"])
    labels = build_labels(orders, reviews)
    assert labels.loc[labels.order_id == "o1", "return_risk"].iloc[0] == 1
    assert labels.loc[labels.order_id == "o1", "label_source"].iloc[0] == "canceled"


def test_build_labels_low_review_is_positive_high_is_negative_neutral_dropped():
    orders = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4"],
        "order_status": ["delivered"] * 4,
    })
    reviews = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4"],
        "review_score": [1, 5, 3, 4],
        "review_creation_date": ["2018-01-01"] * 4,
    })
    labels = build_labels(orders, reviews)
    lookup = labels.set_index("order_id")["return_risk"].to_dict()
    assert lookup["o1"] == 1
    assert lookup["o2"] == 0
    assert lookup["o4"] == 0
    assert "o3" not in lookup  # neutral score dropped, not forced into a class


def test_build_labels_no_review_delivered_order_is_dropped():
    orders = pd.DataFrame({"order_id": ["o1"], "order_status": ["delivered"]})
    reviews = pd.DataFrame(columns=["order_id", "review_score", "review_creation_date"])
    labels = build_labels(orders, reviews)
    assert "o1" not in labels["order_id"].values


def test_validate_proxy_label_enrichment_direction():
    reviews = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4"],
        "review_score": [1, 1, 5, 5],
        "review_comment_message": [
            "quero devolver o produto", "produto veio errado", "adorei, chegou rápido", "excelente",
        ],
    })
    v = validate_proxy_label(reviews)
    # low-score reviews should mention returns/refunds far more than high-score ones
    assert v.low_score_rate > v.high_score_rate
    assert v.enrichment > 1


def test_seller_prior_uses_only_past_orders_not_future():
    """The core leakage check: a seller's very first order must get the
    global base rate (no history yet), not information from an order that
    happens later in time."""
    order_table = pd.DataFrame({
        "order_id": ["o1", "o2", "o3"],
        "seller_id": ["s1", "s1", "s1"],
        "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-02-01", "2018-03-01"]),
    })
    labels = pd.DataFrame({
        "order_id": ["o1", "o2", "o3"],
        "return_risk": [1, 1, 0],  # seller s1's first two orders are bad
    })
    global_rate = 0.1
    out = add_expanding_seller_prior(order_table, labels, global_rate, min_prior_orders_for_trust=1)
    out = out.set_index("order_id")

    # o1 is the seller's first order ever -> must fall back near the global rate,
    # NOT be influenced by o2/o3 which happen later
    assert abs(out.loc["o1", "seller_prior_bad_rate"] - global_rate) < 1e-9

    # o3 comes after two bad orders from this seller -> prior should be elevated
    assert out.loc["o3", "seller_prior_bad_rate"] > global_rate


def test_no_test_orders_precede_train_cutoff():
    """Guards the time-based split contract used in pipeline.py: every test
    row's purchase timestamp must be >= every train row's, by construction
    of sorting + slicing."""
    from return_risk.pipeline import time_based_split

    df = pd.DataFrame({
        "order_id": [f"o{i}" for i in range(10)],
        "order_purchase_timestamp": pd.date_range("2018-01-01", periods=10, freq="D"),
        "return_risk": [0, 1] * 5,
    }).sample(frac=1, random_state=1)  # shuffle to prove sorting happens in build_dataset, not here

    df = df.sort_values("order_purchase_timestamp").reset_index(drop=True)
    train, test, cutoff = time_based_split(df, test_frac=0.3)
    assert train["order_purchase_timestamp"].max() <= test["order_purchase_timestamp"].min()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
