#!/usr/bin/env python3
"""End-to-end: load data -> label -> features -> time-split -> train ->
evaluate -> write reports/metrics.json + reports/figures/*.png + model.joblib

Usage:
    python scripts/run_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from return_risk.evaluate import (  # noqa: E402
    classification_metrics,
    cost_sweep,
    estimate_order_loss,
    feature_importance,
    make_figures,
    make_sensitivity_figure,
    pick_best_threshold,
    rank_metrics,
    success_rate_sensitivity,
)
from return_risk.pipeline import (  # noqa: E402
    ALL_FEATURE_COLUMNS,
    build_dataset,
    load_raw,
    time_based_split,
)
from return_risk.seller_store import compute_seller_snapshot, save_snapshot  # noqa: E402
from return_risk.train import save_model, train_model  # noqa: E402
from return_risk.features import build_order_level_table  # noqa: E402
from return_risk.labeling import build_labels  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
REPORTS_DIR = ROOT / "reports"
PROCESSED_DIR = ROOT / "data" / "processed"
MODEL_PATH = PROCESSED_DIR / "model.joblib"
SELLER_SNAPSHOT_PATH = PROCESSED_DIR / "seller_prior_snapshot.csv"
REFERENCE_STATS_PATH = PROCESSED_DIR / "reference_stats.json"


def main() -> None:
    print("[1/5] Loading data, building labels + leakage-safe features ...")
    df, audit_info = build_dataset(DATA_DIR)
    train_df, test_df, cutoff = time_based_split(df, test_frac=0.2)
    print(f"    labeled orders: {len(df)} | train: {len(train_df)} | test: {len(test_df)}")
    print(f"    time-based split cutoff: {cutoff}")

    print("[2/5] Training HistGradientBoostingClassifier ...")
    model = train_model(train_df)
    save_model(model, MODEL_PATH)

    print("[3/5] Scoring held-out test set ...")
    X_test = test_df[ALL_FEATURE_COLUMNS]
    y_test = test_df["return_risk"].values
    y_prob = model.predict_proba(X_test)[:, 1]

    rmetrics = rank_metrics(y_test, y_prob)
    default_metrics = classification_metrics(y_test, y_prob, threshold=0.5)

    print("[4/5] Cost-sensitive threshold sweep ...")
    potential_loss = estimate_order_loss(test_df).values
    sweep_df = cost_sweep(y_test, y_prob, potential_loss)
    best = pick_best_threshold(sweep_df)
    best_metrics = classification_metrics(y_test, y_prob, threshold=float(best["threshold"]))

    print("[5/5] Feature importance + sensitivity analysis + figures + writing report ...")
    fi_df = feature_importance(model, X_test, pd.Series(y_test), n_repeats=6)
    make_figures(y_test, y_prob, sweep_df, REPORTS_DIR / "figures")

    sensitivity_df = success_rate_sensitivity(y_test, y_prob, potential_loss)
    make_sensitivity_figure(sensitivity_df, REPORTS_DIR / "figures")
    sensitivity_df.to_csv(REPORTS_DIR / "success_rate_sensitivity.csv", index=False)
    breakeven_rows = sensitivity_df[sensitivity_df["best_savings_vs_flag_nothing"] > 0]
    breakeven_rate = (
        float(breakeven_rows["intervention_success_rate"].min())
        if len(breakeven_rows) else None
    )

    report = {
        "data_audit": audit_info,
        "split": {
            "train_n": len(train_df),
            "test_n": len(test_df),
            "cutoff_date": str(cutoff),
            "train_base_rate": round(float(train_df["return_risk"].mean()), 4),
            "test_base_rate": round(float(test_df["return_risk"].mean()), 4),
        },
        "rank_metrics_at_test": rmetrics,
        "metrics_at_default_threshold_0.5": default_metrics,
        "metrics_at_cost_optimal_threshold": best_metrics,
        "cost_model_assumptions": {
            "intervention_cost_per_flag_BRL": 25.0,
            "intervention_success_rate": 0.30,
            "loss_model": "2x total_freight (reverse logistics) + 15% of total_price (restock/margin)",
        },
        "savings_vs_flag_nothing_BRL": best["savings_vs_flag_nothing"],
        "breakeven_intervention_success_rate": breakeven_rate,
        "top_10_features": fi_df.head(10).to_dict(orient="records"),
    }

    REPORTS_DIR.mkdir(exist_ok=True)
    with open(REPORTS_DIR / "metrics.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    sweep_df.to_csv(REPORTS_DIR / "threshold_sweep.csv", index=False)
    fi_df.to_csv(REPORTS_DIR / "feature_importance.csv", index=False)

    print("\n=== SUMMARY ===")
    print(f"ROC-AUC: {rmetrics['roc_auc']}  PR-AUC: {rmetrics['pr_auc']}  (base rate {rmetrics['base_rate']})")
    print(f"Cost-optimal threshold: {best['threshold']}")
    print(f"  precision={best_metrics['precision']}  recall={best_metrics['recall']}  "
          f"flags {best_metrics['n_flagged']}/{len(test_df)} test orders")
    print(f"  estimated savings vs flagging nothing: R$ {best['savings_vs_flag_nothing']:,.2f} "
          f"on {len(test_df)} test-set orders (at 30% intervention success rate)")
    print(f"  breakeven intervention success rate: {breakeven_rate}")
    print(f"\nWrote: {REPORTS_DIR/'metrics.json'}, threshold_sweep.csv, feature_importance.csv, "
          f"success_rate_sensitivity.csv, figures/*.png")
    print(f"Wrote model: {MODEL_PATH}")

    # --- Artifacts needed for live/single-order inference (score.py, api.py) ---
    print("\n[extra] Building seller-prior snapshot + reference stats for inference ...")
    raw = load_raw(DATA_DIR)
    labels_full = build_labels(raw["orders"], raw["reviews"])
    order_table_full = build_order_level_table(
        orders=raw["orders"], items=raw["items"], payments=raw["payments"],
        products=raw["products"], sellers=raw["sellers"], customers=raw["customers"],
        category_translation=raw["category_translation"],
    )
    global_base_rate = float(labels_full["return_risk"].mean())
    snapshot = compute_seller_snapshot(order_table_full, labels_full, global_base_rate)
    save_snapshot(snapshot, global_base_rate, SELLER_SNAPSHOT_PATH)

    reference_stats = {
        "seller_prior_bad_rate_p75": float(train_df["seller_prior_bad_rate"].quantile(0.75)),
        "n_items_p90": float(train_df["n_items"].quantile(0.90)),
        "promised_delivery_days_p90": float(train_df["promised_delivery_days"].quantile(0.90)),
        "freight_ratio_p90": float(train_df["freight_to_price_ratio"].quantile(0.90)),
        "cost_optimal_threshold": float(best["threshold"]),
    }
    PROCESSED_DIR.mkdir(exist_ok=True)
    with open(REFERENCE_STATS_PATH, "w") as f:
        json.dump(reference_stats, f, indent=2)
    print(f"Wrote: {SELLER_SNAPSHOT_PATH}, {REFERENCE_STATS_PATH}")


if __name__ == "__main__":
    main()
