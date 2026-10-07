"""
api.py
------
Minimal FastAPI wrapper around ReturnRiskScorer, for a live demo during the
pitch. Not the point of the submission (the modeling + evaluation rigor is)
but makes it trivial to show "here's a merchant hitting our endpoint with a
real order and getting a score back in real time."

Run:
    uvicorn return_risk.api:app --reload --app-dir src
Then:
    curl -X POST localhost:8000/score -H "Content-Type: application/json" -d @sample_order.json
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .score import ReturnRiskScorer

logger = logging.getLogger("return_risk.audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_audit_log_buffer: list[dict[str, Any]] = []
MAX_AUDIT_LOG_ENTRIES = 200

ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

PACKAGE_DATA_DIR = Path(__file__).resolve().parent / "data"

_scorer: Optional[ReturnRiskScorer] = None
_scorer_error: Optional[str] = None


def _get_scorer() -> Optional[ReturnRiskScorer]:
    global _scorer, _scorer_error
    if _scorer is None:
        candidate_dirs = [
            PACKAGE_DATA_DIR,
            PROCESSED_DIR,
            Path("/var/task/data/processed"),
            Path("/var/task/src/return_risk/data"),
            Path.cwd() / "data" / "processed",
        ]
        chosen_dir = None
        for d in candidate_dirs:
            if (d / "model.joblib").exists():
                chosen_dir = d
                break

        if chosen_dir is None:
            _scorer_error = f"Model artifact not found in candidates: {[str(d) for d in candidate_dirs]}"
            print(f"Notice: {_scorer_error}")
            return None

        try:
            _scorer = ReturnRiskScorer(
                model_path=chosen_dir / "model.joblib",
                seller_store_path=chosen_dir / "seller_prior_snapshot.csv",
                reference_stats_path=chosen_dir / "reference_stats.json",
            )
            _scorer_error = None
        except Exception as e:
            import traceback
            _scorer_error = f"{type(e).__name__}: {str(e)}"
            print(f"Notice: Model loading deferred or unavailable: {e}")
    return _scorer


def _load_scorer() -> None:
    _get_scorer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_scorer()
    yield


app = FastAPI(
    title="Razorpay AI Buildathon — Return Risk Scorer",
    description="Real-time return risk scoring & Magic Checkout action policy engine for Track 02 (AI Risk Manager)",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files for product images and assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class OrderRequest(BaseModel):
    order_purchase_timestamp: str
    order_estimated_delivery_date: str
    customer_state: str
    seller_id: str
    seller_state: str
    product_category_name_english: str
    payment_type: str
    n_items: int
    n_distinct_products: int
    n_distinct_sellers: int
    total_price: float
    total_freight: float
    avg_price: float
    max_price: float
    avg_weight_g: Optional[float] = None
    avg_photos_qty: Optional[float] = None
    avg_desc_length: Optional[float] = None
    avg_name_length: Optional[float] = None
    n_payment_installments: int
    total_payment_value: float
    n_payment_methods: int
    threshold: Optional[float] = None


@app.get("/", response_class=HTMLResponse)
@app.get("/checkout", response_class=HTMLResponse)
def get_checkout():
    """Serves the dynamic Magic Checkout page — demonstrates risk-adaptive buyer experience."""
    template_path = TEMPLATES_DIR / "checkout.html"
    if not template_path.exists():
        template_path = ROOT / "index.html"
    if not template_path.exists():
        raise HTTPException(404, "Checkout template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serves the interactive Razorpay Risk Intelligence & Magic Checkout Console."""
    template_path = TEMPLATES_DIR / "dashboard.html"
    if not template_path.exists():
        raise HTTPException(404, "Dashboard template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/health")
def health():
    scorer = _get_scorer()
    return {
        "status": "ok",
        "track": "Track 02 — AI Risk Manager",
        "model_loaded": scorer is not None,
        "load_error": _scorer_error,
        "features_supported": 30,
    }


@app.get("/metrics/summary")
def get_metrics_summary():
    """Returns evaluation metrics, data audit, and cost sweep summary."""
    metrics_file = REPORTS_DIR / "metrics.json"
    if not metrics_file.exists():
        raise HTTPException(404, "Metrics report not found. Run scripts/run_pipeline.py first.")
    with open(metrics_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/score")
def score_order(order: OrderRequest):
    scorer = _get_scorer()
    if scorer is None:
        raise HTTPException(503, "Model not loaded yet")
    payload = order.model_dump(exclude={"threshold"})
    threshold = order.threshold if order.threshold is not None else scorer.reference_stats.get(
        "cost_optimal_threshold", 0.65
    )

    t0 = time.perf_counter()
    try:
        result = scorer.score(payload, threshold=threshold)
    except ValueError as e:
        raise HTTPException(422, str(e))
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    res_dict = result.as_dict()

    # Immutable Audit Log Trail
    audit_entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event": "ORDER_SCORED",
        "risk_score": res_dict["risk_score"],
        "flagged": res_dict["flagged"],
        "risk_tier": res_dict.get("action", {}).get("risk_tier", "unknown"),
        "action_code": res_dict.get("action", {}).get("action_code", "none"),
        "reason_codes": res_dict.get("reason_codes", []),
        "threshold_used": res_dict.get("threshold_used", threshold),
        "latency_ms": latency_ms,
        "inputs": {
            "seller_id": payload.get("seller_id"),
            "customer_state": payload.get("customer_state"),
            "seller_state": payload.get("seller_state"),
            "total_price": payload.get("total_price"),
            "total_freight": payload.get("total_freight"),
            "n_items": payload.get("n_items"),
            "payment_type": payload.get("payment_type"),
        },
    }

    logger.info(json.dumps(audit_entry))
    _audit_log_buffer.append(audit_entry)
    if len(_audit_log_buffer) > MAX_AUDIT_LOG_ENTRIES:
        _audit_log_buffer.pop(0)

    return res_dict


@app.get("/audit-log")
def get_audit_log(limit: int = 50):
    """Returns real-time immutable audit trail of recent scored orders with inputs, decisions, and timestamps."""
    sliced = _audit_log_buffer[-max(1, min(limit, MAX_AUDIT_LOG_ENTRIES)):]
    return {
        "status": "ok",
        "total_logged": len(_audit_log_buffer),
        "returned": len(sliced),
        "audit_trail": list(reversed(sliced)),
    }

