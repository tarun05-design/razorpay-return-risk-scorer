# Return-Risk Scorer & Magic Checkout Policy Engine

[![Track 02: AI Risk Manager](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-Track%2002%3A%20AI%20Risk%20Manager-0066FF?style=flat-square)](https://razorpay.com/buildathon/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Checkout-00C7B7?style=flat-square&logo=vercel)](https://razorpay-return-risk-scorer.vercel.app/)
[![Defense Only](https://img.shields.io/badge/Architecture-Defense%20Only-10b981?style=flat-square)]()
[![Inference Latency](https://img.shields.io/badge/Latency-%3C%201ms%20(Sub--ms)-38bdf8?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-success?style=flat-square)]()

**Track 02 — AI Risk Manager** · Razorpay AI Buildathon Submission  
*An independent open-source prototype inspired by Razorpay Magic Checkout risk architectures.*

🚀 **Interactive Live Demo**: [https://razorpay-return-risk-scorer.vercel.app/](https://razorpay-return-risk-scorer.vercel.app/)  
📊 **Merchant Risk Console**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)

---

## ⚠️ Data and Limitations

> **Training Data (Brazil vs. India Context)**: This model is trained on the [Brazilian Olist e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (88,554 labeled orders, 2016–2018) because **no public Indian COD/RTO order-level dataset exists**. All model training, feature distributions, and monetary evaluations are strictly computed in **R$ (Brazilian Real)**, the native currency of the dataset. The customer-facing checkout demo localizes unit economics and user experience to Indian e-commerce (UPI, COD, OTP verification) for illustrative Track 02 presentation only. In enterprise deployment, the pipeline accepts domestic merchant order telemetry and COD return history directly.
>
> **Proxy Label Construction**: Olist contains no explicit "RTO/return" boolean column. Return risk is proxied from order cancellations + extreme negative review scores ($\le 2$ stars) containing return/refund language (empirically validated by **56.96× NLP keyword enrichment** over positive reviews). Neutral reviews (score = 3) and unreviewed delivered orders are dropped rather than forced into an artificial binary label.
>
> **Softened Industry Claims**: References to Razorpay Magic Checkout illustrate how real-time risk intelligence can integrate into checkout funnels. RTO reduction figures reported by industry platforms vary significantly by merchant vertical, catalog tier, and operational policy.
>
> **Leak-Free Threshold Tuning**: Tier cutoffs and the cost-optimal decision threshold (0.647) were strictly selected on a **validation slice (the chronological tail of the training period)** without test leakage, and reported on the held-out test set.

---

### One-Command Reproduction

```bash
git clone https://github.com/tarun05-design/razorpay-return-risk-scorer.git && cd razorpay-return-risk-scorer && pip install -r requirements.txt && uvicorn return_risk.api:app --app-dir src --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) for the live risk-adaptive checkout, or [http://localhost:8000/dashboard](http://localhost:8000/dashboard) for the merchant console.

---

## ⚡ Quickstart

```bash
# 1. Clone & install
git clone https://github.com/tarun05-design/razorpay-return-risk-scorer.git
cd razorpay-return-risk-scorer
pip install -r requirements.txt

# 2. Run all unit & integration tests (19 passing)
python -m pytest tests/ -v

# 3. Retrain model and regenerate metrics from scratch (fixed seed=42)
python scripts/run_pipeline.py

# 4. Launch API service
uvicorn return_risk.api:app --app-dir src --port 8000

# 5. Score an order from command line
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d @sample_order.json
```

---

## 🎯 Architecture: Real-Time Scoring & Checkout Policy Engine

The system couples a sub-millisecond, deterministic gradient-boosted classifier with a dynamic action policy engine:

```
[ Merchant Checkout / App ]
            │
            ▼  POST /score (Order JSON: items, freight, sellers, customer state)
┌────────────────────────────────────────────────────────┐
│ FastAPI Inference Service                              │
│                                                        │
│  1. Feature Expansion (promised delivery, split-ship)  │
│  2. O(1) Seller Prior Lookup (historical bad rate)     │
│  3. HistGradientBoosting predict_proba (calibrated)    │
│  4. Rule-based Reason Code Generator                   │
│  5. Action Policy Evaluator (Tier & Intervention)      │
└────────────────────────────────────────────────────────┘
            │
            ▼  JSON Response: { risk_score, flagged, reason_codes, action }
[ Risk-Adaptive Checkout UX ]
  ├── Low Risk (<0.30): Frictionless 1-Click COD
  ├── Moderate Risk (0.30–0.50): Instant ₹50 UPI Discount Nudge
  ├── Elevated Risk (0.50–0.65): Automated 2-Way OTP/WhatsApp Verification
  └── Critical Risk (≥0.65): COD Gated (Prepaid Only to protect reverse freight)
```

### API Hosting & Cold-Start Handling
- **FastAPI Backend**: Fully production-ready with `render.yaml` for Render, `Procfile` for Railway/Heroku, and `api/index.py` with `vercel.json` for serverless environments.
- **Cold-Start Resilience**: The frontend incorporates an asynchronous loading state with a 15-second timeout window to accommodate container wake-ups.
- **Anti-Faking Safety Banner**: The frontend connects live to `POST /score`. If the API is unreachable, it displays a prominent **"OFFLINE MODE"** warning banner rather than silently faking scores.

---

## 🧪 Real Held-Out Test Orders in Demo

Rather than simulated profiles, the interactive demo showcases **four actual held-out orders from the test set**:

| Tier | Test Order ID | Real Model Score | Ground Truth Test Outcome | Checkout Intervention |
|---|---|---|---|---|
| **Low** | `#0046176ff0` | **0.0608** (6.1%) | Delivered cleanly · 0% loss · 5-star review | Approve COD / Zero friction |
| **Moderate** | `#99daacedd8` | **0.4569** (45.7%) | Split-shipment dispute! Missing second parcel | Instant ₹50 UPI prepaid discount |
| **Elevated** | `#64ccc97757` | **0.5353** (53.5%) | 45-day transit to Bahia across 2 sellers · Return requested | Automated WhatsApp/OTP confirmation |
| **Critical** | `#24914fccbc` | **0.7192** (71.9%) | High-risk seller (31.9% bad rate) · Returned refilled cartridges | Gate COD (Prepaid only) |

---

## 📊 Rigorous 3-Way Leak-Free Evaluation

### Chronological Train / Validation / Test Split
To avoid temporal data leakage (where models artificially learn from future orders), the dataset is split chronologically:
- **Train period**: 70,843 orders (first 80% chronologically)
  - **Train slice**: 56,674 orders (first 80% of train period; 2016-09-04 to 2018-03-21)
  - **Validation slice**: 14,169 orders (chronological tail of train period; 2018-03-21 to 2018-05-29)
- **Held-out Test set**: 17,711 orders (completely unseen forward orders; 2018-05-29 to 2018-10-17)

### Grounding Policy Tiers on Validation
1. **0.30 Threshold**: Corresponds to the **90th percentile of predicted risk on validation** (flags top ~5% of orders for a gentle prepaid discount nudge with zero customer drop-off).
2. **0.50 Threshold**: Corresponds to the **98th percentile of predicted risk on validation** (flags top ~1.3% of orders for automated WhatsApp verification).
3. **0.647 Threshold**: The **cost-optimal threshold** derived from financial cost sweep on validation (flags ~0.56% of orders to gate COD completely).

---

## 📈 Final Model Metrics (Seed = 42, Held-Out Test Set)

All metrics below are generated directly by `scripts/run_pipeline.py` and saved to `reports/metrics.json`:

### Overall Ranking Performance
- **Held-Out Test Set Size**: 17,711 orders
- **Test Base Rate**: **11.23%** (1,989 positive return-risk orders)
- **ROC-AUC**: **0.6482**
- **PR-AUC**: **0.2657** (2.37× over baseline)

### Precision & Recall at Top-k Percentiles

| Percentile Flagged | Order Count ($k$) | True Positives | Precision | Recall |
|---|---|---|---|---|
| **Top 1.0%** | 177 | 127 | **71.75%** | 6.39% |
| **Top 5.0%** | 885 | 336 | **37.97%** | 16.89% |
| **Top 10.0%** | 1,771 | 495 | **27.95%** | 24.89% |

### Lift by Decile (Held-Out Test Set)

| Decile | Orders | Positives | Positive Rate | Lift over Base Rate |
|---|---|---|---|---|
| **1 (Highest Risk)** | 1,771 | 495 | **27.95%** | **2.49×** |
| **2** | 1,771 | 267 | 15.08% | 1.34× |
| **3** | 1,771 | 208 | 11.74% | 1.05× |
| **4** | 1,771 | 180 | 10.16% | 0.91× |
| **5** | 1,771 | 192 | 10.84% | 0.97× |
| **6** | 1,771 | 156 | 8.81% | 0.78× |
| **7** | 1,771 | 151 | 8.53% | 0.76× |
| **8** | 1,771 | 112 | 6.32% | 0.56× |
| **9** | 1,771 | 111 | 6.27% | 0.56× |
| **10 (Lowest Risk)** | 1,772 | 117 | 6.60% | 0.59× |

### Policy Tier Distribution (100% of Test Set Accounted For)

| Policy Tier | Risk Range | Test Orders ($N$) | Share (%) | Positives | Actual Positive Rate | Total Potential Loss (R$) |
|---|---|---|---|---|---|---|
| **Low** | `< 0.30` | 16,782 | 94.8% | 1,645 | **9.80%** | R$ 120,533.94 |
| **Moderate** | `0.30 – 0.50` | 694 | 3.9% | 198 | **28.53%** (2.5×) | R$ 28,454.20 |
| **Elevated** | `0.50 – 0.65` | 135 | 0.8% | 57 | **42.22%** (3.8×) | R$ 10,482.37 |
| **Critical** | `≥ 0.65` | 100 | 0.6% | 89 | **89.00%** (7.9×) | R$ 6,055.31 |
| **Total** | — | **17,711** | **100.0%** | **1,989** | **11.23%** | **R$ 165,525.82** |

> Note: Actual positive rate climbs monotonically from **9.80%** in Tier 1 to **89.00%** in Tier 4.

### Classification Threshold Performance

| Metric | Default Threshold (0.500) | Validation-Optimal (0.647) |
|---|---|---|
| **Threshold** | 0.500 | **0.647** |
| **Precision** | 62.13% | **89.11%** |
| **Recall** | 7.34% | **4.52%** |
| **F1 Score** | 0.1313 | **0.0861** |
| **Orders Flagged** | 235 / 17,711 (1.3%) | **101 / 17,711 (0.6%)** |
| **True Positives** | 146 | **90** |
| **False Positives** | 89 | **11** |

---

## 🔍 Top Feature Importances (Permutation on Test Set)

1. `n_items` (0.0447): Unusually large basket sizes are strong correlates of transit and delivery friction.
2. `seller_prior_bad_rate` (0.0254): Historical seller dispute and bad-delivery rate.
3. `n_distinct_sellers` (0.0199): Split-shipment orders multiply logistics failure modes.
4. `total_freight` (0.0175): High freight relative to item price.
5. `price_per_item` (0.0160): Extremely cheap or high-margin unit costs.

---

## 🛡️ Test Suite Summary (19 Tests Passing)

The test suite enforces mathematical invariants, leakage prevention, and API contracts:

- `tests/test_evaluate.py`:
  - `test_tier_counts_sum_to_test_set_size`: Proves policy tier counts sum exactly to 100% of the dataset size.
  - `test_precision_recall_at_top_k_hand_computed`: Verifies top-$k$ precision and recall against hand-computed ground truth.
  - `test_lift_by_decile_preserves_total_orders`: Proves decile bins account for all test rows.
- `tests/test_api.py`:
  - `test_score_response_schema_matches_frontend`: Asserts that `/score` returns every field and data type expected by the frontend.
  - `test_health_endpoint`, `test_checkout_endpoint`, `test_dashboard_endpoint`.
- `tests/test_action_policy.py`:
  - Unit tests for loss calculation and all four policy tiers.
- `tests/test_pipeline.py`:
  - Leakage checks: expanding seller prior strictly uses past orders; no test orders precede train cutoff.

Run the suite:
```bash
python -m pytest tests/ -v
```

---

## 📁 Repository Structure

```
├── api/
│   └── index.py                      # Vercel serverless function entrypoint
├── data/
│   ├── raw/                          # Olist Brazilian E-Commerce dataset
│   └── processed/
│       ├── model.joblib              # Persisted HistGradientBoostingClassifier
│       ├── reference_stats.json      # Validation statistics & thresholds
│       └── seller_prior_snapshot.csv # Seller priors snapshot for O(1) inference
├── reports/
│   ├── figures/                      # ROC, PR, calibration, decile lift, and tier plots
│   ├── metrics.json                  # Complete audit report and evaluated metrics
│   ├── lift_by_decile.csv            # Decile lift table
│   └── policy_tier_distribution.csv  # Test orders across policy tiers
├── scripts/
│   └── run_pipeline.py               # End-to-end 3-way time-split pipeline runner
├── src/return_risk/
│   ├── action_policy.py              # Magic Checkout tier decision logic
│   ├── api.py                        # FastAPI /score, /health, /dashboard endpoints
│   ├── evaluate.py                   # Metrics, cost sweeps, decile lift & top-k
│   ├── features.py                   # Leakage-safe expanding seller prior & features
│   ├── labeling.py                   # Proxy label derivation & NLP validation
│   ├── pipeline.py                   # Dataset builders & 3-way temporal splits
│   ├── score.py                      # Inference wrapper & transparent reason codes
│   ├── train.py                      # Gradient-boosted model training
│   └── templates/                    # Checkout & dashboard HTML templates
├── tests/                            # 19 comprehensive unit & integration tests
├── index.html                        # Standalone interactive checkout demo
├── vercel.json                       # Vercel deployment routing
├── render.yaml                       # Render web service configuration
└── Procfile                          # Process file for cloud container deployment
```

---

## 📜 License & Acknowledgments

Distributed under the MIT License. Built for the **Razorpay AI Buildathon — Track 02 (AI Risk Manager)**.
Dataset courtesy of [Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
