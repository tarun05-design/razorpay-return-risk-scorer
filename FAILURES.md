# FAILURES.md — What Broke and How We Fixed It

> **Post-Mortem & Engineering Audit Log**  
> Razorpay AI Buildathon — Track 02 (AI Risk Manager)  
> *A transparent log of actual failures encountered, root causes diagnosed, fixes applied, and verification evidence.*

---

## 1. Clean-Machine Quickstart Test Suite Import Failure

- **Symptom**: On a fresh clean virtual environment after running `pip install -r requirements.txt`, running `pytest tests/` failed with:
  ```
  No module named pytest
  ```
  After manually installing pytest, running `pytest tests/` failed with:
  ```
  ModuleNotFoundError: No module named 'httpx' (raised inside fastapi.testclient.TestClient)
  ModuleNotFoundError: No module named 'matplotlib' (raised inside tests/test_evaluate.py importing evaluate.py)
  ```
- **Root Cause**: `requirements.txt` originally pinned only runtime packages (`fastapi`, `uvicorn`, `pydantic`, `pandas`, `numpy`, `scikit-learn`, `joblib`), omitting test dependencies (`pytest`, `httpx`) and evaluation reporting libraries (`matplotlib`). A panel judge executing the Quickstart instructions on a clean machine encountered immediate test collection errors.
- **Fix**: Added `pytest>=8.0`, `httpx>=0.27`, and `matplotlib>=3.7` to [requirements.txt](file:///d:/Projects/Return%20Risk%20Scorer/requirements.txt), and updated the Quickstart documentation to use `python -m pytest tests/ -v` to protect against environments where the local script path is not on the user's `$PATH`.
- **How I Verified**: Built a completely isolated clean virtual environment from scratch in a separate directory (`clean_venv`), ran `pip install -r requirements.txt`, and verified that all 20 tests in `tests/` pass with zero hidden steps:
  ```
  ======================= 20 passed in 5.38s =======================
  ```
- **What I'd Do Next**: Add a `.github/workflows/ci.yml` matrix that tests clean installations across Python 3.10, 3.11, 3.12, and 3.14 on Linux, macOS, and Windows runners on every pull request.

---

## 2. Policy Threshold Parameter Discrepancy (0.598 vs. 0.647)

- **Symptom**: In `src/return_risk/action_policy.py`, calling `evaluate_action_policy()` without specifying `cost_optimal_threshold` defaulted to `0.598`, whereas `reference_stats.json`, `evaluate.py`, and `README.md` defined the validation-optimal threshold as `0.647`. Orders with predicted risk between `0.598` and `0.647` were assigned Tier 4 (`DISABLE_COD_PREPAID_ONLY`) instead of Tier 3 (`REQUIRE_WHATSAPP_CONFIRMATION`).
- **Root Cause**: An early validation sweep iteration had identified `0.598` as a candidate threshold. When the final 3-way temporal validation sweep settled on `0.647` (yielding the maximum validation savings of R$ 424.43 vs. R$ 265.24 at 0.598), `reference_stats.json` was updated, but the default argument in `action_policy.py` was left as `0.598`.
- **Fix**: Updated line 59 of [action_policy.py](file:///d:/Projects/Return%20Risk%20Scorer/src/return_risk/action_policy.py#L56-L65) to `cost_optimal_threshold: float = 0.647`, and ensured `score.py` passes `self.reference_stats.get("cost_optimal_threshold", 0.647)` explicitly.
- **How I Verified**: Ran hand-calculated boundary tests at `0.55`, `0.62`, and `0.75`. Tested `tests/test_action_policy.py` and `scripts/demo_smoke_test.py` to confirm that orders in `0.50–0.647` correctly receive `REQUIRE_WHATSAPP_CONFIRMATION`, and only orders $\ge 0.647$ receive `DISABLE_COD_PREPAID_ONLY`.
- **What I'd Do Next**: Implement a single centralized `RiskConfig` singleton loaded at startup so default threshold values cannot diverge across different modules.

---

## 3. Demo Checkout Arithmetic & Basket Item Inconsistency

- **Symptom**: In the interactive checkout demo (`index.html`), the order summary did not show an explicit item count or separate promotion breakdown connecting subtotal, discount, and order total. Furthermore, Scenario 4 (Critical Risk) listed 2 items in the UI array (`HP Original Cartridge` qty 1, `HP Tri-Color Pack` qty 1) while the underlying model payload and ground truth order had `n_items: 3`.
- **Root Cause**: The mock storefront UI had hardcoded the second item as a "Pack of 2" with `qty: 1` rather than setting `qty: 2` at unit price R$ 89.90 ($78.90 + 2 \times 89.90 = 258.70$), and the sidebar lacked an explicit formula reconciling `Items Subtotal - Promotion = Order Total` and `Total Savings`.
- **Fix**:
  1. Updated Scenario 4 items: `HP Original High-Yield` (price 78.90, qty 1) + `HP Tri-Color Original Cartridge` (price 89.90, qty 2), totaling exactly 3 items and ₹258.70 / R$ 258.70.
  2. Added dynamic item count rendering: `Items Total (N items)`.
  3. Added an explicit `Promotion (Prepaid UPI Discount): −₹50.00` line and a prominent green `Total Savings: ₹50.00` banner whenever the moderate-risk UPI nudge is active.
- **How I Verified**: Loaded all 4 scenarios in the demo and ran `scripts/demo_smoke_test.py` and browser inspection: verified that $121.99 - 0 = 121.99$, $182.40 - 50 = 132.40$ (Savings: ₹50), $468.00 - 0 = 468.00$, and $258.70 - 0 = 258.70$.
- **What I'd Do Next**: Add automated Playwright / Cypress UI tests in CI that assert DOM text values for Subtotal, Promotion, and Total match the exact arithmetic.

---

## 4. Scikit-Learn `CyHalfBinomialLoss` Cross-Version Unpickling Shim

- **Symptom**: When loading `model.joblib` trained on scikit-learn 1.8.0 under newer environments (such as scikit-learn 1.9+ or Python 3.14 on Vercel), `joblib.load()` crashed with:
  ```
  ModuleNotFoundError: No module named 'sklearn._loss._loss'
  # or: AttributeError: Can't get attribute 'CyHalfBinomialLoss' on <module '_loss'>
  ```
- **Root Cause**: Scikit-learn moved and refactored internal C-extension Cython modules (`sklearn._loss._loss` vs `sklearn._loss.loss`) between minor releases. Because `HistGradientBoostingClassifier` pickles its internal loss function directly, cross-version unpickling fails if the internal module path shifted.
- **Fix**: Added an unpickling compatibility shim inside `ReturnRiskScorer.__init__` in [score.py](file:///d:/Projects/Return%20Risk%20Scorer/src/return_risk/score.py#L112-L125) that dynamically aliases `sys.modules["_loss"]` and `sys.modules["_loss.loss"]` before unpickling.
- **How I Verified**: Successfully unpickled `model.joblib` and ran full inference across Python 3.14.3 with scikit-learn 1.9.1 in the clean virtual environment without errors.
- **What I'd Do Next**: Save model parameters as lightweight JSON weights or ONNX format (`skl2onnx`) for production runtime inference, avoiding pickle serialization entirely.

---

## 5. Lack of Immutable Audit Logging for Checkout Decisions

- **Symptom**: While `/score` computed risk scores and policy actions, there was no structured audit trail recording what order inputs were received, which rules fired, or what decision was served at each millisecond timestamp.
- **Root Cause**: The prototype originally focused on offline metric calculation and fast inference, omitting an enterprise-grade compliance audit log.
- **Fix**: Added structured JSON logging to `return_risk.audit` and implemented an in-memory ring buffer accessible via `GET /audit-log` in [api.py](file:///d:/Projects/Return%20Risk%20Scorer/src/return_risk/api.py), capturing:
  - `timestamp_utc`
  - `event: "ORDER_SCORED"`
  - `risk_score`, `risk_tier`, `action_code`
  - `reason_codes`
  - `inputs` (customer state, seller ID, total price, freight, item count)
  - `latency_ms`
- **How I Verified**: Added `test_audit_log_endpoint` to [tests/test_api.py](file:///d:/Projects/Return%20Risk%20Scorer/tests/test_api.py) and confirmed that POSTing an order immediately populates `/audit-log` with the exact inputs and outputs.
- **What I'd Do Next**: Route audit log streams asynchronously to Kafka / AWS Kinesis / ClickHouse for long-term compliance storage and drift monitoring.

---

## 6. [Placeholder for User]: Additional Incident / Fix Log

- **Symptom**: *(Describe what broke or what error message appeared)*
- **Root Cause**: *(Describe why it broke)*
- **Fix**: *(Describe the code or config change made)*
- **How I Verified**: *(Quote command line output or test results)*
- **What I'd Do Next**: *(Describe future hardening steps)*

---

## 7. [Placeholder for User]: Additional Incident / Fix Log

- **Symptom**: *(Describe what broke or what error message appeared)*
- **Root Cause**: *(Describe why it broke)*
- **Fix**: *(Describe the code or config change made)*
- **How I Verified**: *(Quote command line output or test results)*
- **What I'd Do Next**: *(Describe future hardening steps)*
