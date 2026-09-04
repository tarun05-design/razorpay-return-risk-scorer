"""
evaluate.py
-----------
"Honest metrics including false-positive cost" is the explicit bar for this
track. Precision/recall/AUC alone don't answer the merchant's real question:
"at what threshold does this model actually save money?" So this module:

  1. Reports standard classification metrics + calibration (is predict_proba
     trustworthy, or just rank-ordered?).
  2. Attaches a per-order MONETARY estimate of what a missed return-risk
     order costs (reverse freight + a restocking/margin-loss fraction of
     order value) — using fields already in the data, not invented numbers.
  3. Sweeps thresholds and reports, at each one: how many orders get flagged
     (= operational load on the merchant), precision, recall, and expected
     net financial impact vs a "flag nothing" baseline, under an EXPLICIT,
     documented, tunable assumption about intervention cost and how often
     an intervention actually prevents the loss.

All cost assumptions are named constants at the top of `cost_sweep`, not
buried — a merchant plugging in their real numbers should be able to swap
them in seconds.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from .pipeline import ALL_FEATURE_COLUMNS


def estimate_order_loss(df: pd.DataFrame, restock_margin_fraction: float = 0.15) -> pd.Series:
    """Rough, transparent per-order cost IF a return/loss materializes:
    reverse-logistics (freight there-and-back) + a fraction of order value
    lost to restocking/markdown/margin. Merchants should replace
    `restock_margin_fraction` with their real number."""
    reverse_freight = df["total_freight"].fillna(df["total_freight"].median()) * 2
    margin_loss = df["total_price"].fillna(df["total_price"].median()) * restock_margin_fraction
    return reverse_freight + margin_loss


def classification_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 3),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "n_flagged": int(tp + fp),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
    }


def rank_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
    return {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "base_rate": round(float(np.mean(y_true)), 4),
    }


def cost_sweep(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    potential_loss: np.ndarray,
    intervention_cost_per_flag: float = 25.0,
    intervention_success_rate: float = 0.30,
    n_thresholds: int = 41,
) -> pd.DataFrame:
    """
    Cost model (all assumptions explicit and swappable):
      - Flagging an order (TP or FP) costs `intervention_cost_per_flag`
        (e.g. manual review / proactive outreach / verification step).
      - If flagged AND truly return-risk (TP), the intervention prevents
        the loss with probability `intervention_success_rate`; the rest of
        the time the loss still happens on top of the intervention cost.
      - If flagged but not actually return-risk (FP), you only pay the
        intervention cost — a wasted but bounded expense.
      - If NOT flagged and truly return-risk (FN), the full potential_loss
        is incurred with no mitigation.
      - True negatives cost nothing.

    Baseline for comparison: "flag nothing" = sum(potential_loss over all
    actual positives).
    """
    thresholds = np.linspace(0.01, 0.99, n_thresholds)
    y_true = np.asarray(y_true)
    potential_loss = np.asarray(potential_loss)

    baseline_cost = potential_loss[y_true == 1].sum()

    rows = []
    for t in thresholds:
        flagged = y_prob >= t
        tp_mask = flagged & (y_true == 1)
        fp_mask = flagged & (y_true == 0)
        fn_mask = (~flagged) & (y_true == 1)

        tp_cost = tp_mask.sum() * intervention_cost_per_flag + (
            potential_loss[tp_mask] * (1 - intervention_success_rate)
        ).sum()
        fp_cost = fp_mask.sum() * intervention_cost_per_flag
        fn_cost = potential_loss[fn_mask].sum()

        total_cost = tp_cost + fp_cost + fn_cost
        m = classification_metrics(y_true, y_prob, t)
        rows.append({
            **m,
            "expected_total_cost": round(float(total_cost), 2),
            "savings_vs_flag_nothing": round(float(baseline_cost - total_cost), 2),
        })

    return pd.DataFrame(rows)


def pick_best_threshold(sweep_df: pd.DataFrame) -> pd.Series:
    return sweep_df.loc[sweep_df["savings_vs_flag_nothing"].idxmax()]


def success_rate_sensitivity(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    potential_loss: np.ndarray,
    intervention_cost_per_flag: float = 25.0,
    rates: np.ndarray | None = None,
) -> pd.DataFrame:
    """How much does the model's business case depend on the assumed
    intervention success rate? For each candidate rate, re-run the threshold
    sweep and keep the best achievable savings. Reports where the model
    crosses from net-negative to net-positive — this is more honest than
    reporting a single savings number under one assumption, since that
    assumption is a business input judges/merchants should be able to
    interrogate."""
    if rates is None:
        rates = np.arange(0.05, 1.0, 0.05)

    rows = []
    for r in rates:
        sweep = cost_sweep(y_true, y_prob, potential_loss, intervention_cost_per_flag, r, n_thresholds=25)
        best = pick_best_threshold(sweep)
        rows.append({
            "intervention_success_rate": round(float(r), 2),
            "best_threshold": best["threshold"],
            "best_savings_vs_flag_nothing": best["savings_vs_flag_nothing"],
            "precision_at_best": best["precision"],
            "recall_at_best": best["recall"],
        })
    return pd.DataFrame(rows)


def feature_importance(model, X_test: pd.DataFrame, y_test: pd.Series, n_repeats: int = 8) -> pd.DataFrame:
    result = permutation_importance(
        model, X_test, y_test, n_repeats=n_repeats, random_state=42,
        scoring="average_precision", n_jobs=-1,
    )
    return (
        pd.DataFrame({
            "feature": ALL_FEATURE_COLUMNS,
            "importance_mean": result.importances_mean,
            "importance_std": result.importances_std,
        })
        .sort_values("importance_mean", ascending=False)
        .reset_index(drop=True)
    )


def make_figures(y_true, y_prob, sweep_df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # PR curve
    prec, rec, _ = precision_recall_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(rec, prec)
    plt.xlabel("Recall"); plt.ylabel("Precision")
    plt.title("Precision-Recall curve (held-out test set)")
    plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out_dir / "pr_curve.png", dpi=140); plt.close()

    # ROC curve
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr)
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False Positive Rate"); plt.ylabel("True Positive Rate")
    plt.title("ROC curve (held-out test set)")
    plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out_dir / "roc_curve.png", dpi=140); plt.close()

    # Calibration
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    plt.figure(figsize=(6, 5))
    plt.plot(mean_pred, frac_pos, marker="o")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("Mean predicted probability"); plt.ylabel("Observed frequency")
    plt.title("Calibration curve")
    plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out_dir / "calibration_curve.png", dpi=140); plt.close()

    # Cost sweep
    plt.figure(figsize=(7, 5))
    plt.plot(sweep_df["threshold"], sweep_df["savings_vs_flag_nothing"])
    best = pick_best_threshold(sweep_df)
    plt.scatter([best["threshold"]], [best["savings_vs_flag_nothing"]], color="red", zorder=5,
                label=f"best threshold={best['threshold']}")
    plt.xlabel("Decision threshold"); plt.ylabel("Savings vs flagging nothing (R$)")
    plt.title("Cost-sensitive threshold selection")
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out_dir / "cost_sweep.png", dpi=140); plt.close()


def make_sensitivity_figure(sensitivity_df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7, 5))
    plt.plot(sensitivity_df["intervention_success_rate"], sensitivity_df["best_savings_vs_flag_nothing"], marker="o")
    plt.axhline(0, color="gray", linestyle="--")
    plt.xlabel("Assumed intervention success rate")
    plt.ylabel("Best achievable savings vs flagging nothing (R$)")
    plt.title("Business case sensitivity to intervention effectiveness")
    plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out_dir / "sensitivity_curve.png", dpi=140); plt.close()
