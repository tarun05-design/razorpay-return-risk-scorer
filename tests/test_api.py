import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from return_risk.api import app, _load_scorer


@pytest.fixture(scope="module", autouse=True)
def init_scorer():
    _load_scorer()


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert "Track 02" in data["track"]


def test_dashboard_endpoint(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Razorpay Return-Risk Intelligence" in response.text
    assert "text/html" in response.headers["content-type"]


def test_checkout_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Checkout" in response.text
    assert "text/html" in response.headers["content-type"]

    response_co = client.get("/checkout")
    assert response_co.status_code == 200
    assert "Checkout" in response_co.text


def test_score_endpoint(client):
    with open(ROOT / "sample_order.json") as f:
        sample_order = json.load(f)

    response = client.post("/score", json=sample_order)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "flagged" in data
    assert "reason_codes" in data
    assert "action" in data
    assert "action_code" in data["action"]
    assert "potential_order_loss" in data["action"]


def test_score_response_schema_matches_frontend(client):
    """Guarantees that /score response contract strictly matches every field
    and type read by the checkout demo UI."""
    with open(ROOT / "sample_order.json") as f:
        sample_order = json.load(f)

    response = client.post("/score", json=sample_order)
    assert response.status_code == 200
    data = response.json()

    # Core scoring fields
    assert isinstance(data.get("risk_score"), float)
    assert 0.0 <= data["risk_score"] <= 1.0
    assert isinstance(data.get("flagged"), bool)
    assert isinstance(data.get("threshold_used"), float)
    assert isinstance(data.get("reason_codes"), list)
    assert len(data["reason_codes"]) > 0
    for rc in data["reason_codes"]:
        assert isinstance(rc, str)

    # Action policy object
    action = data.get("action")
    assert isinstance(action, dict)
    assert isinstance(action.get("action_code"), str)
    assert isinstance(action.get("action_title"), str)
    assert isinstance(action.get("action_description"), str)
    assert action.get("risk_tier") in ["low", "moderate", "elevated", "critical"]
    assert isinstance(action.get("badge_color"), str)
    assert isinstance(action.get("recommended_intervention"), str)
    assert isinstance(action.get("potential_order_loss"), (int, float))
    assert isinstance(action.get("expected_savings"), (int, float))
    assert isinstance(action.get("merchant_notes"), list)


def test_audit_log_endpoint(client):
    """Verifies that scored orders are captured in the immutable audit trail with
    inputs, tiers, actions, reason codes, and timestamps."""
    with open(ROOT / "sample_order.json") as f:
        sample_order = json.load(f)

    # Score an order
    post_resp = client.post("/score", json=sample_order)
    assert post_resp.status_code == 200

    # Retrieve audit log
    audit_resp = client.get("/audit-log")
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert data["status"] == "ok"
    assert data["total_logged"] >= 1
    assert len(data["audit_trail"]) >= 1

    entry = data["audit_trail"][0]
    assert "timestamp_utc" in entry
    assert "risk_score" in entry
    assert "risk_tier" in entry
    assert "action_code" in entry
    assert "reason_codes" in entry
    assert "inputs" in entry
    assert entry["inputs"]["customer_state"] == sample_order["customer_state"]
    assert "latency_ms" in entry

