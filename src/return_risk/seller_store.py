"""
seller_store.py
----------------
At training time, `seller_prior_bad_rate` is computed as an expanding window
over historical order timestamps (see features.py) — correct for offline
evaluation, but a live scoring service doesn't get to "expand a window" on
each request. It needs the CURRENT snapshot of each seller's track record,
updated as new labeled outcomes arrive.

This module computes and persists that snapshot (as of the end of the
training data) so `score.py` / `api.py` can look sellers up in O(1) at
inference time, with the same global-base-rate shrinkage used in training.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def compute_seller_snapshot(
    order_table: pd.DataFrame,
    labels: pd.DataFrame,
    global_base_rate: float,
    min_prior_orders_for_trust: int = 20,
) -> pd.DataFrame:
    df = order_table.merge(labels[["order_id", "return_risk"]], on="order_id", how="left")
    labeled = df[df["return_risk"].notna()]

    agg = labeled.groupby("seller_id")["return_risk"].agg(["sum", "count"]).reset_index()
    agg.columns = ["seller_id", "bad_orders", "n_orders"]

    k = min_prior_orders_for_trust
    agg["seller_prior_bad_rate"] = (agg["bad_orders"] + k * global_base_rate) / (agg["n_orders"] + k)
    agg["seller_prior_n_orders"] = agg["n_orders"]

    return agg[["seller_id", "seller_prior_bad_rate", "seller_prior_n_orders"]]


def save_snapshot(snapshot: pd.DataFrame, global_base_rate: float, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(path, index=False)
    with open(path.with_suffix(".meta.json"), "w") as f:
        json.dump({"global_base_rate": global_base_rate}, f)


class SellerPriorLookup:
    """Loads the persisted snapshot and answers lookups with fallback to the
    global base rate for unseen/new sellers (cold start)."""

    def __init__(self, path: Path):
        self.snapshot = pd.read_csv(path).set_index("seller_id")
        with open(path.with_suffix(".meta.json")) as f:
            self.global_base_rate = json.load(f)["global_base_rate"]

    def lookup(self, seller_id: str) -> tuple[float, int]:
        if seller_id in self.snapshot.index:
            row = self.snapshot.loc[seller_id]
            return float(row["seller_prior_bad_rate"]), int(row["seller_prior_n_orders"])
        return float(self.global_base_rate), 0
