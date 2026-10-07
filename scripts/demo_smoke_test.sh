#!/usr/bin/env bash
# scripts/demo_smoke_test.sh
# ---------------------------
# End-to-end smoke test for Razorpay Return Risk Scorer demo:
# Boots the FastAPI service, verifies /health, validates all 4 preset
# held-out scenarios against /score, tests HTML routes, and cleanly shuts down.

set -euo pipefail

PORT=${PORT:-8000}
HOST="127.0.0.1"
BASE_URL="http://${HOST}:${PORT}"
PYTHON_BIN="${PYTHON:-python}"

echo "=========================================================="
echo " Starting Return Risk Scorer Demo Smoke Test"
echo "=========================================================="

# 1. Boot background uvicorn server
echo "[1/4] Launching FastAPI backend on ${BASE_URL}..."
$PYTHON_BIN -m uvicorn return_risk.api:app --app-dir src --port "${PORT}" --host "${HOST}" > /dev/null 2>&1 &
SERVER_PID=$!

cleanup() {
  echo "Shutting down background server (PID ${SERVER_PID})..."
  kill "${SERVER_PID}" 2>/dev/null || true
  wait "${SERVER_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# 2. Wait for server /health to be ready
echo "[2/4] Waiting for /health readiness (model loaded)..."
READY=0
for i in {1..30}; do
  RESP=$(curl -s "${BASE_URL}/health" 2>/dev/null || true)
  if echo "$RESP" | grep -q '"model_loaded":true' || echo "$RESP" | grep -q '"model_loaded": true'; then
    READY=1
    echo "      Backend ready after ${i}s. Health check passed."
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "FAIL: Server failed to start or load model within 30 seconds."
  exit 1
fi

# 3. Test all 4 preset held-out scenarios
echo "[3/4] Validating all 4 preset held-out test scenarios..."

# Scenario 1: Low Risk
echo "  -> Testing Scenario 1 (Low Risk - Order #0046176ff0)..."
RESP_LOW=$(curl -s -X POST "${BASE_URL}/score" \
  -H "Content-Type: application/json" \
  -d '{
    "order_purchase_timestamp": "2018-05-29 19:22:17",
    "order_estimated_delivery_date": "2018-06-29 00:00:00",
    "customer_state": "MG", "seller_id": "43f8c9950d11ecd03a0304a49e010da6", "seller_state": "SP",
    "product_category_name_english": "consoles_games", "payment_type": "credit_card",
    "n_items": 1, "n_distinct_products": 1, "n_distinct_sellers": 1,
    "total_price": 121.99, "total_freight": 15.73, "avg_price": 121.99, "max_price": 121.99,
    "avg_weight_g": 150.0, "avg_photos_qty": 1, "avg_desc_length": 41, "avg_name_length": 38,
    "n_payment_installments": 1, "total_payment_value": 137.72, "n_payment_methods": 1
  }')

if ! echo "${RESP_LOW}" | grep -q '"risk_tier":"low"' && ! echo "${RESP_LOW}" | grep -q '"risk_tier": "low"'; then
  echo "FAIL: Scenario 1 did not assign 'low' tier: ${RESP_LOW}"
  exit 1
fi
echo "      PASS: Scenario 1 assigned Tier 'low' (APPROVE_COD)."

# Scenario 2: Moderate Risk
echo "  -> Testing Scenario 2 (Moderate Risk - Order #99daacedd8)..."
RESP_MOD=$(curl -s -X POST "${BASE_URL}/score" \
  -H "Content-Type: application/json" \
  -d '{
    "order_purchase_timestamp": "2018-05-29 19:12:11",
    "order_estimated_delivery_date": "2018-06-29 00:00:00",
    "customer_state": "MG", "seller_id": "289cdb325fb7e7f891c38608bf9e0962", "seller_state": "SP",
    "product_category_name_english": "music", "payment_type": "credit_card",
    "n_items": 2, "n_distinct_products": 2, "n_distinct_sellers": 2,
    "total_price": 182.40, "total_freight": 23.50, "avg_price": 91.20, "max_price": 129.50,
    "avg_weight_g": 425.0, "avg_photos_qty": 1, "avg_desc_length": 442, "avg_name_length": 42,
    "n_payment_installments": 10, "total_payment_value": 205.90, "n_payment_methods": 1
  }')

if ! echo "${RESP_MOD}" | grep -q '"risk_tier":"moderate"' && ! echo "${RESP_MOD}" | grep -q '"risk_tier": "moderate"'; then
  echo "FAIL: Scenario 2 did not assign 'moderate' tier: ${RESP_MOD}"
  exit 1
fi
echo "      PASS: Scenario 2 assigned Tier 'moderate' (NUDGE_PREPAID_UPI)."

# Scenario 3: Elevated Risk
echo "  -> Testing Scenario 3 (Elevated Risk - Order #64ccc97757)..."
RESP_ELE=$(curl -s -X POST "${BASE_URL}/score" \
  -H "Content-Type: application/json" \
  -d '{
    "order_purchase_timestamp": "2018-05-31 10:42:31",
    "order_estimated_delivery_date": "2018-07-16 00:00:00",
    "customer_state": "BA", "seller_id": "7d13fca15225358621be4086e1eb0964", "seller_state": "SP",
    "product_category_name_english": "watches_gifts", "payment_type": "credit_card",
    "n_items": 2, "n_distinct_products": 2, "n_distinct_sellers": 2,
    "total_price": 468.00, "total_freight": 46.69, "avg_price": 234.00, "max_price": 245.00,
    "avg_weight_g": 314.0, "avg_photos_qty": 1, "avg_desc_length": 581, "avg_name_length": 56,
    "n_payment_installments": 5, "total_payment_value": 514.69, "n_payment_methods": 1
  }')

if ! echo "${RESP_ELE}" | grep -q '"risk_tier":"elevated"' && ! echo "${RESP_ELE}" | grep -q '"risk_tier": "elevated"'; then
  echo "FAIL: Scenario 3 did not assign 'elevated' tier: ${RESP_ELE}"
  exit 1
fi
echo "      PASS: Scenario 3 assigned Tier 'elevated' (REQUIRE_WHATSAPP_CONFIRMATION)."

# Scenario 4: Critical Risk
echo "  -> Testing Scenario 4 (Critical Risk - Order #24914fccbc)..."
RESP_CRI=$(curl -s -X POST "${BASE_URL}/score" \
  -H "Content-Type: application/json" \
  -d '{
    "order_purchase_timestamp": "2018-06-20 18:08:56",
    "order_estimated_delivery_date": "2018-07-30 00:00:00",
    "customer_state": "RS", "seller_id": "88460e8ebdecbfecb5f9601833981930", "seller_state": "PR",
    "product_category_name_english": "computers_accessories", "payment_type": "credit_card",
    "n_items": 3, "n_distinct_products": 2, "n_distinct_sellers": 2,
    "total_price": 258.70, "total_freight": 56.12, "avg_price": 86.23, "max_price": 89.90,
    "avg_weight_g": 198.0, "avg_photos_qty": 1, "avg_desc_length": 285, "avg_name_length": 33,
    "n_payment_installments": 4, "total_payment_value": 314.81, "n_payment_methods": 1
  }')

if ! echo "${RESP_CRI}" | grep -q '"risk_tier":"critical"' && ! echo "${RESP_CRI}" | grep -q '"risk_tier": "critical"'; then
  echo "FAIL: Scenario 4 did not assign 'critical' tier: ${RESP_CRI}"
  exit 1
fi
echo "      PASS: Scenario 4 assigned Tier 'critical' (DISABLE_COD_PREPAID_ONLY)."

# 4. Check UI pages
echo "[4/4] Verifying checkout and dashboard web interfaces..."
CODE_CO=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/checkout")
CODE_DASH=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/dashboard")

if [ "$CODE_CO" -ne 200 ] || [ "$CODE_DASH" -ne 200 ]; then
  echo "FAIL: Static routes returned non-200 (checkout=${CODE_CO}, dashboard=${CODE_DASH})"
  exit 1
fi

echo "      PASS: /checkout (${CODE_CO}) and /dashboard (${CODE_DASH}) returned 200 OK."

echo "=========================================================="
echo " ALL SMOKE TESTS PASSED SUCCESSFULLY! "
echo "=========================================================="
