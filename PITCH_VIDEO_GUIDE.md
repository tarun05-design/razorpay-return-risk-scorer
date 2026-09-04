# 🎙️ Razorpay AI Buildathon — 5-Minute Pitch Video Blueprint & Script

**Track 02: AI Risk Manager**  
**Project:** Return-Risk Scorer & Magic Checkout Policy Engine  
**Target Duration:** Exactly 4:30 – 5:00 minutes  
**Format:** Loom / YouTube Unlisted Screen Recording with Face Cam  

---

## 🎯 High-Level Pitch Narrative

| Timestamp | Section | Visual On-Screen | Core Message & Punchline |
|---|---|---|---|
| **0:00 – 0:45** | **The Hook & Problem** | Slide 1: RTO/Return Margin Erosion + Architecture Overview | E-commerce margins are quietly wiped out by returns and RTOs (Return-to-Origin). In India, COD returns cost 25–40% of margins. |
| **0:45 – 1:45** | **The Data Honesty & Proxy Audit** | Slide 2: Olist Label Proxy & 57× NLP Validation | Public data has no "returned" column. We built an honest, NLP-audited proxy showing **57× enrichment** on return language. |
| **1:45 – 2:30** | **Leakage-Proof ML Architecture** | Slide 3: Expanding Seller Prior + Time-Based Split | Zero lookahead bias. Expanding timestamped seller prior + strict held-out time split. Trees chosen over LLMs for sub-ms checkout speed. |
| **2:30 – 3:30** | **Honest Cost Accounting (The Track Bar)** | Slide 4: Cost Sweep Curve & Sensitivity Analysis | False-positive cost isn't hidden. Our model shows breakeven at 35% intervention efficiency and profitable scaling thereafter. |
| **3:30 – 4:30** | **Live Interactive Console Demo** | Screen Recording: Live Web Dashboard (`localhost:8000`) | Live scoring: moving sliders, showing sub-millisecond response, Razorpay Magic Checkout actions (Prepaid Nudge, WhatsApp OTP, COD Gating). |
| **4:30 – 5:00** | **Razorpay Product Fit & Conclusion** | Slide 5: Razorpay Ecosystem Integration | Direct plug-and-play fit with Razorpay Magic Checkout & Optimizer. Defense-only, high throughput, zero hype. |

---

## 📜 Full Word-for-Word Video Script

### [0:00 – 0:45] SECTION 1: The Problem & Razorpay Context

> **Speaker (Facecam + Slide 1):**  
> "Hi everyone, I'm presenting our submission for **Track 02 — AI Risk Manager** at the Razorpay AI Buildathon.
> 
> Across global e-commerce and Indian D2C, returns and RTO (Return-to-Origin) are the single largest silent leak in merchant profitability. In India, Cash on Delivery return rates hover around 20 to 30%, costing merchants 2× freight and dead inventory.
> 
> Razorpay already attacks this with **Magic Checkout**, which uses AI risk scoring to cut RTO by up to 50%. Our goal was to build a strictly defense-only, production-ready **Return-Risk Scorer and Decision Policy Engine** that evaluates orders in real-time at point-of-sale with measured precision, zero data leakage, and honest false-positive cost accounting."

---

### [0:45 – 1:45] SECTION 2: Data Honesty & The 57× NLP Validation

> **Speaker (Slide 2: Dataset & Label Audit):**  
> "The first engineering hurdle was data integrity. The popular Olist Brazilian e-commerce dataset (100k orders) has **no 'returned' column**. Most public projects pretend it does or predict irrelevant proxies.
> 
> Rather than fake a label, we formulated a rigorous proxy: an order is positive for return-risk if it was canceled, or delivered with a 1 or 2-star customer review. We explicitly dropped 3-star neutral reviews and unreviewed orders to prevent label poisoning.
> 
> But we didn't stop there. We validated this proxy against Portuguese natural language customer review comments. Low-score reviews mention refund and return keywords (`devolver`, `estorno`, `cancelamento`) in **20.8%** of cases, compared to only **0.36%** for high-score reviews. That is a **57× enrichment ratio**, proving our proxy captures genuine return and cancellation intent rather than noise."

---

### [1:45 – 2:30] SECTION 3: Zero-Leakage ML Engineering & Model Choice

> **Speaker (Slide 3: Pipeline & Leakage Guards):**  
> "To prevent subtle lookahead leakage that destroys production ML models:
> 1. We engineered an **expanding-window seller prior**: a seller's track record is computed strictly from orders timestamped *before* the current purchase, with Bayesian shrinkage toward the global base rate for thin-history sellers.
> 2. We held out the **last 20% of orders strictly by time** (May 2018 cutoff), reflecting real forward-in-time deployment.
> 
> For modeling, we chose `HistGradientBoostingClassifier`. On mixed tabular order fields, gradient-boosted trees provide superior calibration and sub-millisecond inference (~0.8ms). An LLM here would introduce 800ms+ network latency and hallucination risk into a sub-10ms checkout budget."

---

### [2:30 – 3:30] SECTION 4: Honest False-Positive Cost Model (The Track Bar)

> **Speaker (Slide 4: Cost Sweep & Sensitivity Charts):**  
> "Track 02 explicitly demands: *'Honest metrics including false-positive cost.'*
> 
> On our 17,711 held-out test orders, our model achieves a **PR-AUC of 0.270** against an 11.2% base rate—a **2.4× lift**.
> 
> To evaluate financial impact, we modeled the true merchant unit economics: 2× freight for reverse logistics plus a 15% restocking margin loss. Flagging an order incurs a ₹25 intervention cost.
> 
> At our cost-optimal threshold of **0.598**, precision reaches **78.6%** (114 True Positives vs. 31 False Positives). 
> 
> Rather than claiming unrealistic astronomical savings, our sensitivity analysis shows that under conservative 30% intervention efficacy, the system breaks even, and becomes substantially profitable once intervention success exceeds 35%—for instance, saving thousands of rupees through automated WhatsApp confirmations or dynamic prepaid discounts."

---

### [3:30 – 4:30] SECTION 5: Live Interactive Dashboard & Decision Demo

> **Speaker (Screen Recording: Browser at `http://localhost:8000`):**  
> *(Show browser window with dark-themed dashboard)*  
> "Let's see the system live.
> 
> Here on our interactive console, we can simulate real-time orders hitting our FastAPI backend.
> 
> When we load a **'Risky Split-Shipment'** scenario—an 8-item order split across 3 sellers with high freight and a 35-day delivery window—our risk gauge instantly flags an **84.2% return probability** with a latency of **0.6 milliseconds**.
> 
> Notice how the policy engine doesn't just return a number: it recommends a concrete Razorpay Magic Checkout action: **`DISABLE_COD_PREPAID_ONLY`**, preventing an estimated ₹553 in reverse logistics loss, with transparent reason codes explaining split-shipment and seller risk.
> 
> When we switch to a **'Moderate Risk'** order, the engine shifts to **`NUDGE_PREPAID_UPI`**, recommending an instant ₹50 UPI discount to convert the COD order to prepaid at checkout."

---

### [4:30 – 5:00] SECTION 6: Conclusion & Razorpay Fit

> **Speaker (Facecam + Final Slide):**  
> "In summary, this project delivers:
> - Rigorous, leakage-free ML with 57× validated proxy ground truth.
> - Honest cost sensitivity modeling meeting the Track 02 standard.
> - A sub-millisecond, defense-only decision engine tailored for **Razorpay Magic Checkout**.
> 
> The code, benchmark suite, unit tests, and interactive dashboard are open source in the repository. Thank you, and I look forward to the panel discussion!"

---

## 💡 Anticipated Panel Defense Questions & Winning Answers

### Q1: "Why not use an LLM or Agent for scoring?"
> **Answer:** "For structured tabular classification with 25 numeric and categorical features, gradient boosted trees (`HistGradientBoostingClassifier`) outperform LLMs in accuracy, calibration, determinism, and latency. At checkout, Razorpay needs decisions in <10ms. Our model evaluates in 0.6ms with zero token cost. LLMs belong in text-heavy tracks like chargeback dispute generation, not tabular risk scoring."

### Q2: "How would this transfer from Brazilian Olist data to Indian D2C?"
> **Answer:** "While category names and payment methods differ (e.g. UPI/COD in India vs Boleto in Brazil), the core feature architecture (split shipments, promised delivery windows, seller historical failure rate, freight-to-price ratio) directly reflects Indian e-commerce RTO drivers. The entire pipeline—label audit, expanding seller priors, time-based splits, and cost sweeps—is plug-and-play with Razorpay merchant data."

### Q3: "What if a seller is brand new with zero order history?"
> **Answer:** "Our expanding seller prior implements empirical Bayes shrinkage. A seller with fewer than 5 orders falls back smoothly to the platform global base rate, preventing false accusations against newly onboarded merchants while flagging the uncertainty in the reason codes."
