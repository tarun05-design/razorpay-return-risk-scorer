import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from return_risk.action_policy import (
    compute_order_loss,
    evaluate_action_policy,
)


def test_compute_order_loss():
    # 2x freight (2*20=40) + 15% price (0.15*100=15) = 55.0
    loss = compute_order_loss(total_price=100.0, total_freight=20.0, restock_margin_fraction=0.15)
    assert abs(loss - 55.0) < 1e-4


def test_evaluate_action_policy_low_risk():
    action = evaluate_action_policy(risk_score=0.12, total_price=200.0, total_freight=30.0)
    assert action.action_code == "APPROVE_COD"
    assert action.risk_tier == "low"
    assert action.badge_color == "#10b981"
    assert "None" in action.recommended_intervention


def test_evaluate_action_policy_moderate_risk():
    action = evaluate_action_policy(risk_score=0.38, total_price=500.0, total_freight=50.0)
    assert action.action_code == "NUDGE_PREPAID_UPI"
    assert action.risk_tier == "moderate"
    assert action.badge_color == "#3b82f6"
    assert action.expected_savings > 0


def test_evaluate_action_policy_elevated_risk():
    action = evaluate_action_policy(risk_score=0.55, total_price=800.0, total_freight=100.0)
    assert action.action_code == "REQUIRE_WHATSAPP_CONFIRMATION"
    assert action.risk_tier == "elevated"
    assert action.badge_color == "#f59e0b"


def test_evaluate_action_policy_critical_risk():
    action = evaluate_action_policy(risk_score=0.75, total_price=1200.0, total_freight=150.0)
    assert action.action_code == "DISABLE_COD_PREPAID_ONLY"
    assert action.risk_tier == "critical"
    assert action.badge_color == "#ef4444"
