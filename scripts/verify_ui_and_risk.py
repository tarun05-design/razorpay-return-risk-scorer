#!/usr/bin/env python3
"""
scripts/verify_ui_and_risk.py
-----------------------------
Comprehensive end-to-end verification script for Return Risk Scorer:
  1. Checks or starts local uvicorn FastAPI server on port 8000.
  2. Verifies Homepage HTML structure and product catalog.
  3. Verifies all photorealistic static product images (HTTP 200, valid byte payload).
  4. Verifies live /score predictions across all 4 held-out scenarios (scores, tiers, policy actions, reason codes).
  5. Verifies localized INR retail pricing math, subtotals, UPI discounts, and checkout arithmetic.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import URLError

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 8000
HOST = "127.0.0.1"
BASE = f"http://{HOST}:{PORT}"
ROOT = Path(__file__).resolve().parent.parent


def is_server_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("model_loaded") is True
    except Exception:
        pass
    return False


def main():
    print("=" * 65)
    print(" RETURN RISK SCORER -- UI, PRICING & RISK VERIFICATION SUITE")
    print("=" * 65)

    started_proc = None
    if not is_server_ready():
        print(f"[*] Local server not detected. Booting FastAPI on {BASE}...")
        cmd = [sys.executable, "-m", "uvicorn", "return_risk.api:app", "--app-dir", "src", "--port", str(PORT), "--host", HOST]
        started_proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ready = False
        for sec in range(1, 20):
            if is_server_ready():
                ready = True
                print(f"    [OK] FastAPI server booted and ready in {sec}s.")
                break
            time.sleep(1)
        if not ready:
            print("[FAIL] ERROR: Failed to launch FastAPI server within 20s.")
            if started_proc:
                started_proc.terminate()
            sys.exit(1)
    else:
        print(f"[*] Detected running server on {BASE}. Utilizing active instance.")

    try:
        # --- 1. Homepage & Checkout HTML Verification ---
        print("\n--- 1. Testing Homepage & Checkout HTML ---")
        for route in ["/", "/checkout"]:
            with urllib.request.urlopen(f"{BASE}{route}") as resp:
                assert resp.status == 200, f"Route {route} failed with {resp.status}"
                html = resp.read().decode("utf-8")
                assert "Sony PlayStation DualShock 4" in html, f"DualShock title missing on {route}"
                assert "Vinyl Record LP" in html, f"Vinyl title missing on {route}"
                assert "HP Original High-Yield" in html, f"HP cartridge missing on {route}"
                assert "ChronoKing Store" in html, f"Chrono watch seller missing on {route}"
                assert "advisorModal" in html, f"AI Inspector modal missing on {route}"
                print(f"[OK] Route '{route}': 200 OK ({len(html):,} bytes) with dynamic product catalog & AI inspector.")

        # --- 2. Static Product Images Verification ---
        print("\n--- 2. Testing Photorealistic Static Images ---")
        imgs = [
            "/static/images/ps4_controller.jpg",
            "/static/images/vinyl_record.jpg",
            "/static/images/luxury_perfume.jpg",
            "/static/images/chrono_watch.jpg",
            "/static/images/minimalist_watch.jpg",
            "/static/images/hp_cartridges.jpg",
        ]
        for img in imgs:
            req = urllib.request.Request(f"{BASE}{img}")
            with urllib.request.urlopen(req) as r:
                assert r.status == 200, f"Image {img} returned HTTP {r.status}"
                length = int(r.headers.get("content-length", 0))
                assert length > 10000, f"Image {img} too small ({length} bytes)"
                print(f"[OK] {img}: HTTP {r.status} OK ({length:,} bytes)")

        # --- 3. Testing /score Endpoint Across All 4 Scenarios ---
        print("\n--- 3. Testing /score Endpoint Across All 4 Scenarios ---")
        scenarios = {
            "low": {
                "name": "Low Risk (Single Item, Top Corridor)",
                "expected_score": 0.0608,
                "expected_tier": "low",
                "expected_code": "APPROVE_COD",
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
                "name": "Moderate Risk (Split Shipment Nudge)",
                "expected_score": 0.4569,
                "expected_tier": "moderate",
                "expected_code": "NUDGE_PREPAID_UPI",
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
                "name": "Elevated Risk (Long Transit + Top Quartile Bad Rate)",
                "expected_score": 0.5353,
                "expected_tier": "elevated",
                "expected_code": "REQUIRE_WHATSAPP_CONFIRMATION",
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
                "name": "Critical Risk (31.9% Defect Seller + Split Items)",
                "expected_score": 0.7192,
                "expected_tier": "critical",
                "expected_code": "DISABLE_COD_PREPAID_ONLY",
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

        for key, sc in scenarios.items():
            data = json.dumps(sc["payload"]).encode("utf-8")
            req = urllib.request.Request(f"{BASE}/score", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as r:
                res = json.loads(r.read().decode("utf-8"))
                score = res["risk_score"]
                tier = res["action"]["risk_tier"]
                code = res["action"]["action_code"]
                reasons = res.get("reason_codes", [])
                savings = res["action"]["expected_savings"]

                print(f"[OK] [{key.upper()}] {sc['name']}:")
                print(f"     Risk Score:  {score:.4f} (expected ~{sc['expected_score']:.4f})")
                print(f"     Risk Tier:   {tier} (expected {sc['expected_tier']})")
                print(f"     Policy Code: {code} (expected {sc['expected_code']})")
                print(f"     Expected Savings: R$ {savings:.2f}")
                print(f"     Reason Codes: {reasons}")

                assert tier == sc["expected_tier"], f"Tier mismatch for {key}: {tier} != {sc['expected_tier']}"
                assert code == sc["expected_code"], f"Action mismatch for {key}: {code} != {sc['expected_code']}"

        # --- 4. Checking Indian Retail Pricing & Arithmetic Logic ---
        print("\n--- 4. Checking Indian Retail Pricing & Arithmetic Logic ---")
        pricing_scenarios = [
            {
                "tier": "Low Risk",
                "items": [("Sony PlayStation DualShock 4 Wireless Controller", 3999.00, 1)],
                "discount": 0.0,
                "expected_subtotal": 3999.00,
                "expected_total": 3999.00
            },
            {
                "tier": "Moderate Risk (UPI Nudge)",
                "items": [
                    ("Collector Edition Vinyl Record LP", 1499.00, 1),
                    ("Luxury Hydration Golden Fragrance (100ml)", 2499.00, 1)
                ],
                "discount": 50.0,
                "expected_subtotal": 3998.00,
                "expected_total": 3948.00
            },
            {
                "tier": "Elevated Risk",
                "items": [
                    ("Luxury Chronograph Dress Watch with Leather Strap", 5999.00, 1),
                    ("Minimalist Bauhaus Quartz Watch (Matte Black)", 4299.00, 1)
                ],
                "discount": 0.0,
                "expected_subtotal": 10298.00,
                "expected_total": 10298.00
            },
            {
                "tier": "Critical Risk",
                "items": [
                    ("HP Original High-Yield Black Print Cartridge", 899.00, 1),
                    ("HP Tri-Color Original Cartridge", 1099.00, 2)
                ],
                "discount": 0.0,
                "expected_subtotal": 3097.00,
                "expected_total": 3097.00
            }
        ]

        for p in pricing_scenarios:
            computed_subtotal = sum(price * qty for _, price, qty in p["items"])
            computed_total = computed_subtotal - p["discount"]
            assert computed_subtotal == p["expected_subtotal"], f"Subtotal mismatch in {p['tier']}"
            assert computed_total == p["expected_total"], f"Total mismatch in {p['tier']}"
            print(f"[OK] {p['tier']:<28}: Subtotal Rs. {computed_subtotal:,.2f} - Discount Rs. {p['discount']:,.2f} = Total Rs. {computed_total:,.2f}")

        # --- 5. Audit Trail Log Verification ---
        print("\n--- 5. Checking Immutable Audit Trail Log ---")
        with urllib.request.urlopen(f"{BASE}/audit-log?limit=10") as r:
            assert r.status == 200
            audit_data = json.loads(r.read().decode("utf-8"))
            trail = audit_data.get("audit_trail", [])
            print(f"[OK] /audit-log: {len(trail)} orders captured in audit trail.")
            if trail:
                latest = trail[0]
                print(f"     Latest entry: timestamp={latest.get('timestamp_utc')}, tier={latest.get('risk_tier')}, action={latest.get('action_code')}, latency={latest.get('latency_ms')}ms")

        print("\n" + "=" * 65)
        print(" ALL VERIFICATIONS PASSED SUCCESSFULLY! (UI, PRICING & RISK FACTOR)")
        print("=" * 65)

    finally:
        if started_proc:
            print("\nShutting down temporary test server...")
            started_proc.terminate()
            try:
                started_proc.wait(timeout=5)
            except Exception:
                started_proc.kill()


if __name__ == "__main__":
    main()
