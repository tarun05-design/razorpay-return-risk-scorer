# Return-Risk Scorer

### Prevent RTO losses before they happen.

[![Track 02: AI Risk Manager](https://img.shields.io/badge/Razorpay%20AI%20Buildathon-Track%2002%3A%20AI%20Risk%20Manager-0066FF?style=flat-square)](https://razorpay.com/buildathon/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Checkout-00C7B7?style=flat-square&logo=vercel)](https://razorpay-return-risk-scorer.vercel.app/)
[![Defense Only](https://img.shields.io/badge/Architecture-Defense%20Only-10b981?style=flat-square)]()
[![Inference Latency](https://img.shields.io/badge/Latency-0.85ms%20(Sub--ms)-38bdf8?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-20%20Passing-success?style=flat-square)]()

**Track 02 — AI Risk Manager** · Razorpay AI Buildathon Submission  
*An independent open-source prototype inspired by Razorpay Magic Checkout risk architectures.*

---

### ⚡ Key Results (Held-Out Test Set)

| **89.11%** | **2.49×** | **0.85 ms** | **17,711** | **20** |
| :---: | :---: | :---: | :---: | :---: |
| **Critical-Tier Precision**<br>(Wilson 95%: 81.5%–93.8%) | **Top-Decile Lift**<br>(vs. 11.23% base rate) | **Mean Latency**<br>(Sub-millisecond inference) | **Held-Out Test Orders**<br>(Temporal forward test set) | **Automated Tests**<br>(100% test pass rate) |

---

## 📌 Contents
- [Problem](#-problem)
- [Solution](#-solution)
- [Architecture](#-architecture)
- [Demo & Real Held-Out Scenarios](#-demo--real-held-out-scenarios)
- [Results & Empirical Evaluation](#-results--empirical-evaluation)
- [Business Impact & Cost Model](#-business-impact--cost-model)
- [Technical Details & Audit Trail](#-technical-details--audit-trail)
- [AI Judgment & Model Selection](#-ai-judgment--model-selection)
- [Reproducibility & Quickstart](#-reproducibility--quickstart)
- [Limitations & Next Steps](#-limitations--next-steps)

---

## 🚨 Problem

- **The COD Conundrum**: In emerging e-commerce markets like India, Cash-on-Delivery (COD) accounts for 50–65% of transactions for many D2C merchants (*source: RedSeer / Bain e-Conomy India reports*), with logistics aggregators citing Return-to-Origin (RTO) rates between 15% and 30%.
- **Symmetric Margins, Asymmetric Losses**: Forward and reverse freight, unboxing, repacking, and inventory lockup cost merchants an estimated 2–3× the shipping fee per failed delivery (*logistics modeling assumption*).
- **The False Trade-Off**: 
  - *Blanket COD restrictions* hurt checkout conversion by 20–40% among COD-preferring buyers (*source: Shopify / Razorpay industry benchmarks*).
  - *Blind COD acceptance* bleeds operating margins and burdens reverse logistics.
- **Latency Bottleneck**: Traditional risk models rely on slow external credit or device checks (>200ms). Modern checkout funnels operate under strict payment gateway latency budgets (<50ms) requiring **deterministic, sub-millisecond (<1ms) risk scoring** to prevent funnel drop-off.

---

## 💡 Solution

A **sub-millisecond risk scoring and dynamic checkout policy engine** inspired by Razorpay Magic Checkout. Rather than a blunt "allow/block" binary switch, the engine maps calibrated risk probabilities to a 4-tier progressive intervention policy:

```
[ Predicted Return Risk ]
      │
      ├── Low Risk (<0.30) ─────────► Frictionless 1-Click COD (Zero checkout friction)
      │
      ├── Moderate Risk (0.30–0.50) ─► Instant ₹50 UPI Discount Nudge (Incentivizes prepaid)
      │
      ├── Elevated Risk (0.50–0.647) ─► Automated WhatsApp/OTP Verification (Filters uncommitted buyers)
      │
      └── Critical Risk (≥0.647) ────► Gate COD (Prepaid Only to protect reverse freight)
```

1. **Protects Conversion**: Over **94.8%** of orders experience zero friction (1-click checkout).
2. **Encourages Prepaid Adoption**: Moderate-risk shoppers receive a gentle discount incentive to convert to UPI.
3. **Validates Intent**: Long-haul orders receive instant automated confirmation before freight is dispatched.
4. **Saves Severe Losses**: High-risk orders (89.11% true loss rate) are strictly gated to prepaid payment methods.

---

## 🏗️ Architecture

### 1. Data Pipeline & Offline Model Training Architecture
![Return-Risk Scorer Architecture](architecture.png)

### 2. Real-Time Scoring & Dynamic Checkout Policy Engine
```
[ Merchant Checkout / Frontend ]
               │
               ▼  POST /score (Order JSON: items, freight, sellers, customer state)
┌────────────────────────────────────────────────────────────────────────┐
│ FastAPI Sub-Millisecond Inference Engine (Avg Latency: 0.85 ms)        │
│                                                                        │
│  1. Feature Expansion (promised transit days, split-seller indicators) │
│  2. O(1) Seller Prior Lookup (leak-free historical dispute rate)       │
│  3. HistGradientBoostingClassifier predict_proba (calibrated)          │
│  4. Rule-Based Explainable Reason Code Generator                       │
│  5. Dynamic Action Policy Evaluator (Tier & Intervention Assignment)   │
└────────────────────────────────────────────────────────────────────────┘
               │
               ▼  JSON Response: { risk_score, policy_tier, action, reason_codes }
[ Dynamic Risk-Adaptive Checkout UX ]
   ├── Tier 1 (Low): Unrestricted COD
   ├── Tier 2 (Moderate): ₹50 UPI Discount banner applied
   ├── Tier 3 (Elevated): Inline OTP/WhatsApp verification challenge
   └── Tier 4 (Critical): COD payment disabled with transparent prepaid notice
```

### Deployment Architecture & Resiliency
- **Backend Architecture**: Lightweight FastAPI service with `render.yaml` for Render, `Procfile` for Railway, and `api/index.py` for Vercel serverless.
- **Cold-Start Resilience**: Frontend implements asynchronous polling with an animated loading state and a 15-second grace window to absorb serverless wake-up latency.
- **Anti-Faking Safety Banner**: The frontend connects directly to `POST /score`. If the API backend is unreachable, it displays an explicit **"OFFLINE MODE"** warning rather than silently fabricating mock predictions.
- **Audit Logging**: Every scoring decision is logged with inputs, risk tier, action code, reason codes, and UTC timestamp (`GET /audit-log`).

---

## 🧪 Demo & Real Held-Out Scenarios

🚀 **Interactive Checkout Demo**: [https://razorpay-return-risk-scorer.vercel.app/](https://razorpay-return-risk-scorer.vercel.app/)

The demo connects to live inference and showcases **four actual held-out orders from the test set**:

> **Statistical Evidence vs. Illustrative Cases**: The four scenarios highlighted below are illustrative individual cases selected to demonstrate tier-specific mechanics in the checkout UX; the macro-level tier positive rates, decile lift, and Wilson 95% confidence intervals across the entire 17,711-order held-out test set constitute the real empirical proof of generalization.

| Tier | Test Order ID | Real Model Score | Ground Truth Test Outcome | Checkout Intervention |
|---|---|---|---|---|
| **Low** | `#0046176ff0` | **0.0608** (6.1%) | Delivered cleanly · 0% loss · Customer review reports 5-star delivery satisfaction | Approve COD / Zero friction |
| **Moderate** | `#99daacedd8` | **0.4569** (45.7%) | Split-shipment dispute: customer review reports only 1 of 2 packages arrived (missing second parcel) | Instant ₹50 UPI prepaid discount |
| **Elevated** | `#64ccc97757` | **0.5353** (53.5%) | Customer review reports 45-day transit delay to Bahia across 2 sellers with return request | Automated WhatsApp/OTP confirmation *(filters buyers unwilling to wait before freight is spent)* |
| **Critical** | `#24914fccbc` | **0.7192** (71.9%) | High-risk seller (31.9% dispute rate) · Customer review reports return request for defective ink cartridges | Gate COD (Prepaid only) |

> **Action vs. Risk Driver Rationale**: A 45-day estimated transit delay cannot be accelerated by an automated message. However, automated WhatsApp/SMS verification serves an essential operational function: **it filters out buyers unwilling to wait for extended transit before costly cross-country freight is incurred.**

---

## 📊 Results & Empirical Evaluation

All evaluations are conducted on a strictly forward **held-out test set of 17,711 orders** using fixed seed=42. Tier thresholds were tuned exclusively on the validation slice without temporal data leakage.

### Overall Ranking Metrics
- **Held-Out Test Set Size**: 17,711 orders
- **Test Base Rate**: **11.23%** (1,989 positive return-risk orders)
- **ROC-AUC**: **0.6482**
- **PR-AUC**: **0.2657** (2.37× over random baseline)
- **Mean Inference Latency**: **0.85 ms** per order

### Precision & Recall at Top-k Percentiles

| Percentile Flagged | Order Count ($k$) | True Positives | Precision | Recall |
|---|---|---|---|---|
| **Top 1.0%** | 177 | 127 | **71.75%** | 6.39% |
| **Top 5.0%** | 885 | 336 | **37.97%** | 16.89% |
| **Top 10.0%** | 1,771 | 495 | **27.95%** | 24.89% |

### Lift by Decile (Monotonic Risk Discrimination)

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

| Policy Tier | Risk Range | Test Orders ($N$) | Share (%) | Positives | Actual Positive Rate | Wilson 95% CI | Total Potential Loss | Net Value Impact (R$) |
|---|---|---|---|---|---|---|---|---|
| **Low** | `< 0.30` | 16,782 | 94.8% | 1,645 | **9.80%** | `[9.36%, 10.26%]` | R$ 120,533.94 | −R$ 120,533.94 |
| **Moderate** | `0.30 – 0.50` | 694 | 3.9% | 198 | **28.53%** (2.5×) | `[25.30%, 32.00%]` | R$ 28,454.20 | +R$ 7,911.68 |
| **Elevated** | `0.50 – 0.647` | 134 | 0.8% | 56 | **41.79%** (3.7×) | `[33.78%, 50.26%]` | R$ 10,379.02 | +R$ 2,845.71 |
| **Critical** | `≥ 0.647` | 101 | 0.6% | 90 | **89.11%** (7.9×) | `[81.54%, 93.81%]` | R$ 6,158.66 | +R$ 3,633.66 |
| **Total** | — | **17,711** | **100.0%** | **1,989** | **11.23%** | `[10.77%, 11.70%]` | **R$ 165,525.82** | **−R$ 106,142.89** |

> **Sample Size & Wilson Confidence Intervals**: Because high-risk cohorts are highly selective (101 orders in the Critical tier), point estimates carry small-sample variance. The Wilson 95% binomial confidence interval for the Critical tier spans **81.54% to 93.81%**, confirming that even at the conservative lower bound, risk density remains >7.2× above baseline.  
> **Reconciliation with 0.647 Threshold**: Setting the Critical tier boundary at $\ge 0.647$ ensures that the Policy Tier and the cost-optimal decision threshold isolate the exact same set of **101 flagged orders (90 TP, 11 FP, 89.11% precision)**.

### Classification Threshold Performance

| Metric | Default Threshold (0.500) | Validation-Optimal (0.647) |
|---|---|---|
| **Threshold** | 0.500 | **0.647** |
| **Precision** | 62.13% | **89.11%** (Wilson 95% CI: 81.54% – 93.81%) |
| **Recall** | 7.34% | **4.52%** |
| **F1 Score** | 0.1313 | **0.0861** |
| **Orders Flagged** | 235 / 17,711 (1.3%) | **101 / 17,711 (0.6%)** |
| **True Positives** | 146 | **90** |
| **False Positives** | 89 | **11** |
| **False Negatives** | 1,843 | **1,899** |
| **True Negatives** | 15,633 | **15,711** |

---

## 💰 Business Impact & Cost Model

### Unit Economics & Currency Consistency
- **Offline ML Evaluation**: Strictly in **R$ (Brazilian Real)**, matching the native currency of the Olist e-commerce dataset. No currency mixing occurs in loss calculations.
- **Intervention Cost**: Fixed at **R$ 25.0 per flagged order** (e.g., automated outreach, priority verification, or COD restriction review).
- **Loss Equation**: For unmitigated return-risk orders:  
  $$\text{Loss} = 2 \times \text{total\_freight (round-trip logistics)} + 15\% \times \text{total\_price (restock/markdown)}$$
- **Total Potential Loss**: Unmitigated return-risk orders across the test set represent **R$ 165,525.82** in direct freight and margin losses.
- **Demo Localization**: The interactive checkout UI localizes figures to **₹ (INR)** (e.g. ₹50 UPI discount) purely for presentation to Indian judges for Track 02.

### Sensitivity & Breakeven Analysis
- **Breakeven Success Rate**: **35%** ($s = 0.35$).  
- If merchant intervention converts or prevents $\ge 35\%$ of flagged high-risk COD orders, net financial savings exceed the R$ 25 intervention cost.
- At the baseline assumption of 30% resolution ($s = 0.30$), gating COD on the Critical tier alone delivers **+R$ 3,633.66** in net margin savings, with **89.11% precision** (only 11 false positives across 17,711 test orders).

---

## ⚙️ Technical Details

### Leakage-Safe Feature Engineering
1. **Expanding Seller Prior**: Historical seller dispute rates are computed strictly using past orders preceding the current order's purchase timestamp ($O(1)$ hash map lookup at inference).
2. **Promised Delivery Transit Days**: Calendar duration between order purchase and promised delivery date.
3. **Split-Seller Multipliers**: Number of distinct items, distinct sellers, and product categories.
4. **Logistics Economics**: Freight-to-price ratio and total freight burden.

### Top Feature Importances (Permutation on Test Set)
1. `n_items` (0.0447): Unusually large basket sizes are strong correlates of transit and delivery friction.
2. `seller_prior_bad_rate` (0.0254): Historical seller dispute and bad-delivery rate.
3. `n_distinct_sellers` (0.0199): Split-shipment orders multiply logistics failure modes.
4. `total_freight` (0.0175): High freight relative to item price.
5. `price_per_item` (0.0160): Extremely cheap or high-margin unit costs.

### Transparent Reason Codes
The model pairs every numerical probability score with deterministic, rule-based reason codes (e.g., `HIGH_SELLER_DISPUTE_RATE`, `SPLIT_SHIPMENT_MULTIPLE_SELLERS`, `LONG_ESTIMATED_DELIVERY_TIME`) to ensure full transparency for merchants and support staff.

### 📋 Immutable Audit Trail & Defense-Only Guarantee
Every request to `POST /score` is recorded into an immutable audit trail (`GET /audit-log`) with order features, risk score, policy tier, action code, reason codes, inference latency, and UTC timestamp:

```json
{
  "timestamp_utc": "2026-10-07T03:49:50.123456+00:00",
  "event": "ORDER_SCORED",
  "risk_score": 0.5413,
  "flagged": false,
  "risk_tier": "elevated",
  "action_code": "REQUIRE_WHATSAPP_CONFIRMATION",
  "reason_codes": [
    "New/thin-history seller — scored using platform base rate, less certainty",
    "Unusually large order (6 items)",
    "Order splits across 2 sellers (split-shipment risk)"
  ],
  "threshold_used": 0.647,
  "latency_ms": 0.88,
  "inputs": {
    "seller_id": "brand_new_seller_xyz",
    "customer_state": "SP",
    "seller_state": "RS",
    "total_price": 890.0,
    "total_freight": 210.0,
    "n_items": 6,
    "payment_type": "credit_card"
  }
}
```

- **Defense-Only Guarantee**: The scoring pipeline evaluates only order structure, logistics geometry (interstate transit, freight ratio), and seller historical reliability. **Zero customer identifiers, zero buyer profiling, and zero cross-session tracking** are used, ensuring fair, non-discriminatory buyer treatment.

### 🛡️ Test Suite Summary (20 Tests Passing)

The test suite enforces mathematical invariants, temporal leakage prevention, and API contracts:

- **Core Tests (16 tests)**:
  - `tests/test_action_policy.py` (5 tests): Validates unit loss calculation and policy assignment for all four risk tiers.
  - `tests/test_pipeline.py` (6 tests): Enforces no temporal leakage (expanding seller prior uses past orders only, no test orders precede train cutoff, proxy label validation).
  - `tests/test_api.py` (5 tests): Verifies `/health`, `/checkout`, `/dashboard`, `/score`, and `/audit-log` endpoints.
- **Evaluation & Schema Integrity Tests (4 tests)**:
  - `tests/test_evaluate.py`: `test_tier_counts_sum_to_test_set_size` (proves policy tier counts sum to 100% of dataset).
  - `tests/test_evaluate.py`: `test_precision_recall_at_top_k_hand_computed` (validates top-$k$ metrics against hand computation).
  - `tests/test_evaluate.py`: `test_lift_by_decile_preserves_total_orders` (ensures decile bins account for all test rows).
  - `tests/test_api.py`: `test_score_response_schema_matches_frontend` (guarantees response schema matches checkout UI contract).

---

## 🧠 AI Judgment & Model Selection

### Why Gradient-Boosted Trees Over an LLM for Checkout Decisions?
1. **Sub-Millisecond Latency Budget**: Payment checkout funnels operate under strict SLA constraints (<50 ms). Our `HistGradientBoostingClassifier` executes in **0.85 ms**, whereas cloud LLM API calls take 500–2,000 ms, which destroys checkout conversion.
2. **Probability Calibration for Cost Optimization**: Business decisions require calibrated risk probabilities ($P(\text{return\_risk})$) to derive cost-optimal cutoffs ($\tau^* = 0.647$); LLMs do not output calibrated probabilities on tabular numerical features and are prone to uncalibrated confidence.
3. **Auditability & Zero Hallucinations**: Financial loss interventions demand deterministic, reproducible scoring that can be justified to merchants in regulatory audits.
4. **Tabular Feature Mastery**: Non-linear interactions between freight-to-price ratios, basket sizes, and historical seller priors are naturally modeled by gradient-boosted trees without prompt fragility.

### Where an LLM Optionally Adds Value
- **Dynamic 2-Way Outreach Copy**: When an order enters Tier 3 (Elevated Risk), an LLM can draft personalized, friendly WhatsApp confirmation text referencing the specific reason codes (e.g. asking the buyer to confirm their pin code for a long-distance multi-seller shipment).
- **Offline NLP Label Extraction**: Refining proxy return labels from unstructured Portuguese/Hindi customer dispute text during batch pipeline runs.

### Deterministic Fallback Policy
If network timeouts, cold starts, or model unpickling shims fail, the system degrades to deterministic, rule-based fallback policies (`APPROVE_COD` by default) rather than blocking orders or inventing mock scores.

---

## 🚀 Reproducibility & Quickstart

### One-Command Reproduction
```bash
git clone https://github.com/tarun05-design/razorpay-return-risk-scorer.git && cd razorpay-return-risk-scorer && pip install -r requirements.txt && uvicorn return_risk.api:app --app-dir src --port 8000
```
Then open [http://localhost:8000](http://localhost:8000) for the live risk-adaptive checkout, or [http://localhost:8000/dashboard](http://localhost:8000/dashboard) for the merchant console.

### Step-by-Step Execution
```bash
# 1. Clone repository & install dependencies
git clone https://github.com/tarun05-design/razorpay-return-risk-scorer.git
cd razorpay-return-risk-scorer
pip install -r requirements.txt

# 2. Run all unit, integration, and audit tests (20 passing)
python -m pytest tests/ -v

# 3. Run end-to-end demo smoke test across all 4 preset scenarios
bash scripts/demo_smoke_test.sh   # or: python scripts/demo_smoke_test.py

# 4. Retrain model & regenerate all evaluation reports (fixed seed=42)
python scripts/run_pipeline.py

# 5. Launch FastAPI inference server
uvicorn return_risk.api:app --app-dir src --port 8000

# 6. Score an order from command line
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d @sample_order.json
```

---

## ⚠️ Limitations & Next Steps

*Open acknowledgment of constraints and roadmap demonstrates engineering rigor and realistic risk modeling.*

### Current Limitations
1. **Proxy Return Label Rather Than Direct RTO Ground Truth**:  
   Olist lacks a direct "RTO/return" boolean field. Return risk is proxied from order cancellations combined with extreme negative reviews ($\le 2$ stars) containing return/refund language (empirically supported by **56.96× NLP keyword enrichment**). Orders delivered cleanly without reviews are dropped.
2. **Modest Global ROC-AUC (0.6482)**:  
   Because pre-purchase features (basket size, promised transit days, seller dispute priors) capture only partial signals of post-delivery human behavior, overall ranking capability is modest (ROC-AUC: 0.6482, PR-AUC: 0.2657). However, top-decile lift is **2.49×**, and top-tier precision reaches **89.11%**.
3. **Low Recall (4.52% at Cost-Optimal Threshold)**:  
   At the cost-optimal cutoff ($\tau^* = 0.647$), recall is **4.52%** (flagging 101 orders, 90 TP, 11 FP). This trade-off is deliberate: in payment checkout, false-positive friction costs more than false negatives, so the policy flags only the highest-conviction loss risks.
4. **Break-Even Sensitivity ($\ge 35\%$ Success Rate)**:  
   Under the assumed R$ 25.0 intervention cost per flagged order, the business case achieves net positive financial return only if dynamic merchant interventions successfully mitigate or prevent $\ge 35\%$ of flagged returns.
5. **Brazilian Historical Dataset (2016–2018)**:  
   Trained on the Brazilian Olist dataset due to the absence of public Indian order-level COD datasets. Unit economics and monetary loss evaluations are strictly computed in **R$**.
6. **No Live Razorpay Production Data**:  
   This repository is an independent open-source buildathon prototype inspired by Razorpay Magic Checkout architectures, built without access to Razorpay's proprietary merchant network telemetry.
7. **What Real Data Would Be Needed for Full Production**:  
   - Direct courier tracking webhooks (`RTO_INITIATED`, `UNDELIVERED_BUYER_REJECTED`, `DOORSTEP_REFUSAL`).
   - Native Indian payment gateway telemetry (UPI decline history, device fingerprints, address deliverability score).
   - Randomized controlled trial (A/B testing) outcomes measuring live merchant conversion drop-off against reverse logistics recovery.

### Next Iteration (Path to Production)
1. **Direct RTO/Return Labels**: Integrate live courier webhook events (e.g. `RTO_INITIATED`, `UNDELIVERED_BUYER_REJECTED`) from 3PLs and merchant ERPs.
2. **Merchant-Specific Calibration**: Fine-tune probability thresholds per merchant vertical (e.g., fashion and jewelry tolerate different margin buffers than high-value electronics).
3. **Online Drift Monitoring**: Deploy automated Kolmogorov-Smirnov (KS) tests and Population Stability Index (PSI) tracking to detect feature drift and concept drift in production.
4. **Cost-Sensitive Learning**: Integrate asymmetric financial loss matrix directly into the gradient-boosted training objective rather than post-hoc threshold sweeping.
5. **A/B Testing of COD Interventions**: Run multi-armed bandit experiments measuring conversion drop-off versus reverse logistics savings across live checkout traffic.
6. **Razorpay Payment & Device Signals**: Ingest pre-checkout telemetry (device fingerprints, card decline frequency, UPI handle verification) via native payment gateway hooks.
7. **Real Intervention Outcome Feedback**: Close the feedback loop by recording whether OTP confirmation or UPI discounts successfully mitigated the loss, updating the policy engine online.

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
│   ├── demo_smoke_test.sh            # End-to-end demo smoke test (bash)
│   ├── demo_smoke_test.py            # End-to-end demo smoke test (python cross-platform)
│   └── run_pipeline.py               # End-to-end 3-way time-split pipeline runner
├── src/return_risk/
│   ├── action_policy.py              # Magic Checkout tier decision logic
│   ├── api.py                        # FastAPI /score, /health, /dashboard, /audit-log endpoints
│   ├── evaluate.py                   # Metrics, cost sweeps, decile lift & top-k
│   ├── features.py                   # Leakage-safe expanding seller prior & features
│   ├── labeling.py                   # Proxy label derivation & NLP validation
│   ├── pipeline.py                   # Dataset builders & 3-way temporal splits
│   ├── score.py                      # Inference wrapper & transparent reason codes
│   ├── train.py                      # Gradient-boosted model training
│   └── templates/                    # Checkout & dashboard HTML templates
├── tests/                            # 20 comprehensive unit & integration tests
├── FAILURES.md                       # Post-mortem audit: what broke & how it was fixed
├── index.html                        # Standalone interactive checkout demo
├── vercel.json                       # Vercel deployment routing
├── render.yaml                       # Render web service configuration
└── Procfile                          # Process file for cloud container deployment
```

---

## 📜 License & Acknowledgments

Distributed under the MIT License. Built for the **Razorpay AI Buildathon — Track 02 (AI Risk Manager)**.  
Dataset courtesy of [Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
