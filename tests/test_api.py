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
