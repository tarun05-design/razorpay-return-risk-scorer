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
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .score import ReturnRiskScorer

ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Razorpay AI Buildathon — Return Risk Scorer",
    description="Real-time return risk scoring & Magic Checkout action policy engine for Track 02 (AI Risk Manager)",
    version="1.0.0",
)

# Mount static files for product images and assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_scorer: Optional[ReturnRiskScorer] = None


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


def _get_scorer() -> Optional[ReturnRiskScorer]:
    global _scorer
    if _scorer is None:
        try:
            _scorer = ReturnRiskScorer(
                model_path=PROCESSED_DIR / "model.joblib",
                seller_store_path=PROCESSED_DIR / "seller_prior_snapshot.csv",
                reference_stats_path=PROCESSED_DIR / "reference_stats.json",
            )
        except Exception as e:
            print(f"Notice: Model loading deferred or unavailable: {e}")
    return _scorer


@app.on_event("startup")
def _load_scorer() -> None:
    _get_scorer()


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
        "cost_optimal_threshold", 0.598
    )
    try:
        result = scorer.score(payload, threshold=threshold)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return result.as_dict()

