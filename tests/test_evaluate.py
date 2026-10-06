import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from return_risk.evaluate import (
    precision_recall_at_top_k,
    policy_tier_distribution,
    lift_by_decile,
)


def test_tier_counts_sum_to_test_set_size():
    """Guarantees that policy_tier_distribution assigns every single order
    to exactly one tier, so tier counts sum to the total dataset size."""
    n = 250
    np.random.seed(42)
    y_true = np.random.choice([0, 1], size=n, p=[0.85, 0.15])
    y_prob = np.random.uniform(0.01, 0.99, size=n)
    potential_loss = np.random.uniform(20.0, 150.0, size=n)
    total_price = np.random.uniform(50.0, 500.0, size=n)
    total_freight = np.random.uniform(10.0, 50.0, size=n)

    tier_df = policy_tier_distribution(
        y_true=y_true,
        y_prob=y_prob,
        potential_loss=potential_loss,
        total_price=total_price,
        total_freight=total_freight,
        cost_optimal_threshold=0.65,
    )

    # Check sum of orders across tiers equals total test-set size
    assert tier_df["n_orders"].sum() == n
    # Check sum of positives across tiers equals total true positives
    assert tier_df["n_positives"].sum() == int(y_true.sum())
    # Check percentages sum to ~100%
    assert abs(tier_df["pct_of_all_orders"].sum() - 100.0) < 0.5


def test_precision_recall_at_top_k_hand_computed():
    """Deterministic hand-computed example:
    10 orders, exactly 3 positives (at ranks 1, 3, 7).
    Order 0: prob=0.95, true=1
    Order 1: prob=0.85, true=0
    Order 2: prob=0.75, true=1
    Order 3: prob=0.65, true=0
    Order 4: prob=0.55, true=0
    Order 5: prob=0.45, true=0
    Order 6: prob=0.35, true=1
    Order 7: prob=0.25, true=0
    Order 8: prob=0.15, true=0
    Order 9: prob=0.05, true=0

    Top 10% (k=1):
      Order 0 selected -> TP=1, k=1 -> Precision=1.0000, Recall=1/3 = 0.3333

    Top 20% (k=2):
      Orders 0, 1 selected -> TP=1, k=2 -> Precision=0.5000, Recall=1/3 = 0.3333

    Top 30% (k=3):
      Orders 0, 1, 2 selected -> TP=2, k=3 -> Precision=2/3 = 0.6667, Recall=2/3 = 0.6667
    """
    y_true = np.array([1, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    y_prob = np.array([0.95, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15, 0.05])

    results = precision_recall_at_top_k(y_true, y_prob, percentiles=(0.10, 0.20, 0.30))

    # Top 10%
    top10 = results[0]
    assert top10["k"] == 1
    assert top10["true_positives"] == 1
    assert abs(top10["precision"] - 1.0000) < 1e-4
    assert abs(top10["recall"] - 0.3333) < 1e-4

    # Top 20%
    top20 = results[1]
    assert top20["k"] == 2
    assert top20["true_positives"] == 1
    assert abs(top20["precision"] - 0.5000) < 1e-4
    assert abs(top20["recall"] - 0.3333) < 1e-4

    # Top 30%
    top30 = results[2]
    assert top30["k"] == 3
    assert top30["true_positives"] == 2
    assert abs(top30["precision"] - 0.6667) < 1e-4
    assert abs(top30["recall"] - 0.6667) < 1e-4


def test_lift_by_decile_preserves_total_orders():
    n = 100
    y_true = np.array([1] * 20 + [0] * 80)
    y_prob = np.linspace(0.99, 0.01, n)

    decile_df = lift_by_decile(y_true, y_prob)
    assert len(decile_df) == 10
    assert decile_df["n_orders"].sum() == n
    assert decile_df["n_positives"].sum() == 20
    # Decile 1 should have highest lift
    assert decile_df.iloc[0]["lift"] > 1.0
