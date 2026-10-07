#!/usr/bin/env python3
"""
scripts/demo_smoke_test.py
--------------------------
Cross-platform end-to-end smoke test for Razorpay Return Risk Scorer demo:
Boots the FastAPI server, tests /health, sends all 4 preset held-out scenarios to /score,
verifies UI routes (/checkout, /dashboard), and cleanly terminates the server.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

PORT = 8000
HOST = "127.0.0.1"
BASE_URL = f"http://{HOST}:{PORT}"

ROOT = Path(__file__).resolve().parent.parent

SCENARIOS = {
    "low": {
        "expected_tier": "low",
        "expected_action": "APPROVE_COD",
        "payload": {
            "order_purchase_timestamp": "2018-05-29 19:22:17",
            "order_estimated_delivery_date": "2018-06-29 00:00:00",
            "customer_state": "MG", "seller_id": "43f8c9950d11ecd03a0304a49e010da6", "seller_state": "SP",
            "product_category_name_english": "consoles_games", "payment_type": "credit_card",
            "n_items": 1, "n_distinct_products": 1, "n_distinct_sellers": 1,
            "total_price": 121.99, "total_freight": 15.73, "avg_price": 121.99, "max_price": 121.99,
            "avg_weight_g": 150.0, "avg_photos_qty": 1, "avg_desc_length": 41, "avg_name_length": 38,
            "n_payment_installments": 1, "total_payment_value": 137.72, "n_payment_methods": 1
        }
    },
    "moderate": {
        "expected_tier": "moderate",
        "expected_action": "NUDGE_PREPAID_UPI",
        "payload": {
            "order_purchase_timestamp": "2018-05-29 19:12:11",
            "order_estimated_delivery_date": "2018-06-29 00:00:00",
            "customer_state": "MG", "seller_id": "289cdb325fb7e7f891c38608bf9e0962", "seller_state": "SP",
            "product_category_name_english": "music", "payment_type": "credit_card",
            "n_items": 2, "n_distinct_products": 2, "n_distinct_sellers": 2,
            "total_price": 182.40, "total_freight": 23.50, "avg_price": 91.20, "max_price": 129.50,
            "avg_weight_g": 425.0, "avg_photos_qty": 1, "avg_desc_length": 442, "avg_name_length": 42,
            "n_payment_installments": 10, "total_payment_value": 205.90, "n_payment_methods": 1
        }
    },
    "elevated": {
        "expected_tier": "elevated",
        "expected_action": "REQUIRE_WHATSAPP_CONFIRMATION",
        "payload": {
            "order_purchase_timestamp": "2018-05-31 10:42:31",
            "order_estimated_delivery_date": "2018-07-16 00:00:00",
            "customer_state": "BA", "seller_id": "7d13fca15225358621be4086e1eb0964", "seller_state": "SP",
            "product_category_name_english": "watches_gifts", "payment_type": "credit_card",
            "n_items": 2, "n_distinct_products": 2, "n_distinct_sellers": 2,
            "total_price": 468.00, "total_freight": 46.69, "avg_price": 234.00, "max_price": 245.00,
            "avg_weight_g": 314.0, "avg_photos_qty": 1, "avg_desc_length": 581, "avg_name_length": 56,
            "n_payment_installments": 5, "total_payment_value": 514.69, "n_payment_methods": 1
        }
    },
    "critical": {
        "expected_tier": "critical",
        "expected_action": "DISABLE_COD_PREPAID_ONLY",
        "payload": {
            "order_purchase_timestamp": "2018-06-20 18:08:56",
            "order_estimated_delivery_date": "2018-07-30 00:00:00",
            "customer_state": "RS", "seller_id": "88460e8ebdecbfecb5f9601833981930", "seller_state": "PR",
            "product_category_name_english": "computers_accessories", "payment_type": "credit_card",
            "n_items": 3, "n_distinct_products": 2, "n_distinct_sellers": 2,
            "total_price": 258.70, "total_freight": 56.12, "avg_price": 86.23, "max_price": 89.90,
            "avg_weight_g": 198.0, "avg_photos_qty": 1, "avg_desc_length": 285, "avg_name_length": 33,
            "n_payment_installments": 4, "total_payment_value": 314.81, "n_payment_methods": 1
        }
    }
}


def main():
    print("=" * 60)
    print(" Starting Return Risk Scorer Demo Smoke Test")
    print("=" * 60)

    # 1. Boot background server
    print(f"[1/4] Launching FastAPI backend on {BASE_URL}...")
    cmd = [sys.executable, "-m", "uvicorn", "return_risk.api:app", "--app-dir", "src", "--port", str(PORT), "--host", HOST]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # 2. Poll /health
        print("[2/4] Waiting for /health readiness (model loaded)...")
        ready = False
        for sec in range(1, 31):
            try:
                with urlopen(f"{BASE_URL}/health", timeout=2) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        if data.get("model_loaded") is True:
                            ready = True
                            print(f"      Backend ready in {sec}s. Health check passed.")
                            break
            except Exception:
                pass
            time.sleep(1)

        if not ready:
            print("FAIL: Backend server failed to start or load model within 30s.")
            sys.exit(1)

        # 3. Test 4 preset scenarios
        print("[3/4] Validating all 4 preset held-out test scenarios...")
        for name, sc in SCENARIOS.items():
            req_data = json.dumps(sc["payload"]).encode("utf-8")
            req = Request(f"{BASE_URL}/score", data=req_data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=5) as resp:
                assert resp.status == 200, f"HTTP {resp.status} on {name}"
                res = json.loads(resp.read().decode())
                tier = res["action"]["risk_tier"]
                action = res["action"]["action_code"]
                score = res["risk_score"]
                print(f"  -> Scenario {name.title()}: score={score:.4f}, tier={tier}, action={action}")
                assert tier == sc["expected_tier"], f"Expected tier {sc['expected_tier']}, got {tier}"
                assert action == sc["expected_action"], f"Expected action {sc['expected_action']}, got {action}"
                print(f"      PASS: Scenario '{name}' verified.")

        # 4. Verify web endpoints
        print("[4/4] Verifying HTML web interfaces...")
        for path in ["/", "/checkout", "/dashboard"]:
            with urlopen(f"{BASE_URL}{path}", timeout=3) as resp:
                assert resp.status == 200, f"Failed on {path}"
                content = resp.read().decode()
                assert len(content) > 1000, f"Empty content on {path}"
                print(f"      PASS: {path} returned 200 OK ({len(content)} bytes).")

        print("=" * 60)
        print(" ALL SMOKE TESTS PASSED SUCCESSFULLY! ")
        print("=" * 60)

    finally:
        print("Shutting down background server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
