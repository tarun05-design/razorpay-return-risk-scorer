# Return-Risk Scorer & Magic Checkout Policy Engine

[![Track 02: AI Risk Manager](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-Track%2002%3A%20AI%20Risk%20Manager-0066FF?style=flat-square)](https://razorpay.com/buildathon/)
[![Defense Only](https://img.shields.io/badge/Architecture-Defense%20Only-10b981?style=flat-square)]()
[![Inference Latency](https://img.shields.io/badge/Latency-%3C%201ms%20(Sub--ms)-38bdf8?style=flat-square)]()
[![Proxy Validation](https://img.shields.io/badge/NLP%20Audit-57%C3%97%20Enrichment-f59e0b?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-14%20Passing-success?style=flat-square)]()

**Track 02 — AI Risk Manager** · Razorpay AI Buildathon  
*Stop the merchant losing money to fraud, returns and chargebacks.*

A production-oriented verifier that scores an e-commerce order's probability of turning into a return/refund/cancellation-style loss, at order time — with a measured precision/recall on a held-out test set, an honest false-positive cost sensitivity model, and an automated **Razorpay Magic Checkout** policy action engine.

![architecture](architecture.png)

---

## ⚡ Quickstart: Launch Interactive Merchant Console

Experience the real-time scoring simulator and Magic Checkout policy engine in your browser:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit test suite (14 passing tests)
python -m pytest tests/ -v

# 3. Launch the Razorpay Risk Console & API
uvicorn return_risk.api:app --app-dir src --port 8000
```
Open **`http://localhost:8000`** in your browser to interact with the live order simulator, dynamic threshold adjuster, and ROI visualizer.

---

## 🧭 Alignment with Razorpay & Magic Checkout

In Indian e-commerce and global D2C, **Return-to-Origin (RTO)** and doorstep delivery rejections eat **25–40% of merchant operating margins**. Razorpay's flagship D2C product, **Magic Checkout**, tackles this by reducing RTO by up to 50% through AI risk scoring.

This project directly bridges raw probability scores to concrete, bounded checkout policies:

| Risk Tier | Score Range | Magic Checkout Action | Financial Rationale |
|---|---|---|---|
| **Low** | `< 0.30` | `APPROVE_COD` | 1-click frictionless checkout. Zero barrier for safe orders. |
| **Moderate** | `0.30 – <0.50` | `NUDGE_PREPAID_UPI` | Offer instant ₹50 / 5% UPI discount to convert COD to prepaid, eliminating RTO risk before shipping. |
| **Elevated** | `0.50 – <0.65` | `REQUIRE_WHATSAPP_CONFIRMATION` | Trigger automated WhatsApp/SMS interactive address & buyer confirmation. |
| **Critical** | `>= 0.65` | `DISABLE_COD_PREPAID_ONLY` | Restrict to online prepayment to save merchant from 2× freight loss and inventory lockup. |

---

## 🔍 The Core Problem This Project Actually Solves

Olist's public dataset (100K real Brazilian e-commerce orders, 2016–2018) has **no "returned" flag**. Most public projects using this dataset predict customer churn or LTV, not returns — because *the label doesn't exist*. Building a return-risk scorer here requires being explicit about a proxy definition of return-risk and proving it's not noise. This repo constructs and validates that proxy label.

### Proxy Label Definition (The Design Decision That Matters Most)

| Class | Rule |
|---|---|
| **Positive (proxy return-risk)** | `order_status == 'canceled'`, OR a delivered order with `review_score ∈ {1, 2}` |
| **Negative (proxy low-risk)** | delivered order with `review_score ∈ {4, 5}` |
| **Dropped** | `review_score == 3` (neutral — forcing it into a class would poison the label), delivered orders with no review, non-terminal statuses (shipped/processing/etc. — outcome not yet known) |

### 57× NLP Validation (Evidence, Not Assertion)
Review text is never used as a *feature* (it's written after delivery — that would leak), but it's used once to check whether the *label* means what we claim. Searching review comments for Portuguese return/refund/cancellation language (`devolv-`, `troca`, `reembols-`, `estorn-`, `cancel-`, …):

- Low-score (1–2) reviews mention returns/refunds/cancellations **20.8%** of the time
- High-score (4–5) reviews mention them **0.36%** of the time
- **57× enrichment** — the proxy tracks real return-adjacent language, not noise

Full breakdown: `reports/metrics.json → data_audit.proxy_label_validation`.

---

## 🛡️ Leakage-Safe Engineering by Construction

1. **Features Knowable Pre-Order Only**: Item count, price, freight, weight, payment installments, category, promised delivery window (estimated − purchase date, not actual delivery), and interstate shipping flag.
2. **Expanding Seller Prior**: Naively averaging a seller's outcomes over all orders leaks the future. Instead, we use an **expanding window ordered by purchase timestamp** with empirical Bayes shrinkage toward the global base rate for thin-history sellers. Unit-tested in `tests/test_pipeline.py`.
3. **Time-Based Split (Held-Out Test Set)**: The evaluation strictly holds out the **last 20% of orders by purchase date** (cutoff: 2018-05-29), testing the model as it would operate in real-world deployment.

---

## 🚀 Model Architecture & Latency Benchmark

We use `sklearn.HistGradientBoostingClassifier` to score 30 pre-order tabular features (26 numeric + 4 categorical).

### Why Trees Over LLMs for Real-Time Checkout?
For this project, we use a <10ms checkout-latency target as a benchmark context. Our measured scorer latency is substantially below that target. Tabular gradient-boosted trees provide calibrated probabilities with sub-millisecond execution, while an LLM would introduce 800ms+ network latency and non-deterministic hallucination risk.

Run the latency benchmark tool:
```bash
python scripts/benchmark.py --n-runs 3000
```

**Benchmark Results:**
- **Mean Latency**: `0.85 ms` (Single Core)
- **p95 Latency**: `1.20 ms`
- **Throughput**: `1,170+ orders/sec`
- **Result**: **10× headroom** under the <10ms benchmark target.

---

## 📊 Results (Held-Out Test Set, 17,711 Orders)

| Metric | Value | Context |
|---|---|---|
| **ROC-AUC** | **0.647** | Rank-ordering signal on pre-outcome signals |
| **PR-AUC** | **0.270** | **~2.4× lift** over 11.2% base rate |
| **Calibration** | **0.131 vs. 0.112** | Mean predicted vs. true rate (well-calibrated probabilities) |

At the **Cost-Optimal Threshold (0.598)**:
- **Precision**: `78.6%` (114 True Positives vs. 31 False Positives)
- **Recall**: `5.7%` (Orders flagged: 145 / 17,711 = 0.8%)

### Honest Cost Accounting (The Explicit Track Bar)

Per-order potential loss: `2 × total_freight` (reverse logistics) + `15% × total_price` (restock/margin loss). Intervention cost: ₹25 / flag.

- At a conservative **30% intervention success rate**, the cost-optimal threshold nets **−₹89.55** vs. flagging nothing on the test set (breakeven).
- Our sensitivity sweep (`reports/success_rate_sensitivity.csv`) shows the model becomes **net-positive once intervention effectiveness passes ~35%** (e.g. saving ₹4,800+ on test batch with WhatsApp verification or UPI discounts).

All figures: `reports/figures/` (PR curve, ROC curve, calibration curve, cost sweep, sensitivity curve).

---

## 📁 Repository Structure

```
├── src/return_risk/
│   ├── action_policy.py      # Razorpay Magic Checkout policy rules & financial ROI
│   ├── api.py                # FastAPI endpoints (/score, /health, /dashboard)
│   ├── evaluate.py           # Metrics, cost sweep, sensitivity curves, plots
│   ├── features.py           # Leakage-safe feature engineering & expanding seller prior
│   ├── labeling.py           # Proxy label construction & 57x NLP validation
│   ├── pipeline.py           # Dataset assembly & time-based split
│   ├── score.py              # Single-order verifier & plain-language reason codes
│   ├── seller_store.py       # Persisted seller-prior lookup
│   ├── templates/
│   │   └── dashboard.html    # Razorpay-themed interactive merchant console
│   └── train.py              # HistGradientBoostingClassifier training & export
├── scripts/
│   ├── benchmark.py          # Latency & throughput benchmarking suite
│   ├── download_data.py      # Automated dataset downloader
│   ├── download_data.sh      # Bash download script
│   └── run_pipeline.py       # Full training, evaluation & artifact generation
├── tests/
│   ├── test_action_policy.py # Policy engine & ROI unit tests
│   ├── test_api.py           # FastAPI routes & integration tests
│   └── test_pipeline.py      # Label logic, proxy validation & leakage guards
├── reports/                  # metrics.json, threshold_sweep.csv, figures/
├── sample_order.json         # Example real-time order payload
└── architecture.png          # System architecture diagram
```

---

## 🔒 Scope Discipline & Defense-Only Guarantee

**Strictly defense-only**, per the Razorpay Track 02 bar. This system scores and flags risk for merchant loss prevention and checkout safety — nothing here identifies, targets, or acts against individual customers, and there is no component that could be repurposed to manipulate payment outcomes.
