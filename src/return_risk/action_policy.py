"""
action_policy.py
----------------
Translates continuous, calibrated return-risk probabilities into bounded,
actionable merchant checkout policies — directly aligned with Razorpay Magic
Checkout and Razorpay AI Risk Manager architectures.

Rather than giving a merchant an ungrounded raw number, this module provides:
  1. Concrete policy tiers (Allow COD, Prepaid Nudge, WhatsApp Verification, Block COD)
  2. Financial impact analysis (potential order loss vs. intervention ROI)
  3. Action audit trail for merchant ops / automated checkout gates
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class PolicyAction:
    action_code: str
    action_title: str
    action_description: str
    risk_tier: str  # 'low', 'moderate', 'elevated', 'critical'
    badge_color: str
    recommended_intervention: str
    potential_order_loss: float
    expected_savings: float
    merchant_notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_code": self.action_code,
            "action_title": self.action_title,
            "action_description": self.action_description,
            "risk_tier": self.risk_tier,
            "badge_color": self.badge_color,
            "recommended_intervention": self.recommended_intervention,
            "potential_order_loss": round(self.potential_order_loss, 2),
            "expected_savings": round(self.expected_savings, 2),
            "merchant_notes": self.merchant_notes,
        }


def compute_order_loss(
    total_price: float,
    total_freight: float,
    restock_margin_fraction: float = 0.15,
) -> float:
    """Calculates potential unrecovered loss if return/RTO occurs:
    2x freight (forward + reverse logistics) + restocking/margin loss."""
    return float(max(0.0, (2 * total_freight) + (total_price * restock_margin_fraction)))


def evaluate_action_policy(
    risk_score: float,
    total_price: float = 100.0,
    total_freight: float = 20.0,
    cost_optimal_threshold: float = 0.598,
    intervention_cost: float = 25.0,
    intervention_success_rate: float = 0.30,
) -> PolicyAction:
    """
    Evaluates policy tiers based on calibrated probability and merchant unit economics:

    - Tier 1 (risk < 0.30): APPROVE_COD
      Low risk. 1-click frictionless checkout.

    - Tier 2 (0.30 <= risk < 0.50): NUDGE_PREPAID_UPI
      Moderate risk. Offer dynamic 5% / ₹50 discount to convert COD to prepaid UPI,
      eliminating RTO risk at point of sale.

    - Tier 3 (0.50 <= risk < cost_optimal_threshold or 0.70): REQUIRE_WHATSAPP_CONFIRMATION
      Elevated risk. Trigger automated WhatsApp/SMS interactive address & delivery intent check.

    - Tier 4 (risk >= cost_optimal_threshold): DISABLE_COD_PREPAID_ONLY
      High risk. Restrict payment method to prepaid to guard reverse logistics margin.
    """
    potential_loss = compute_order_loss(total_price, total_freight)

    if risk_score < 0.30:
        expected_savings = 0.0
        return PolicyAction(
            action_code="APPROVE_COD",
            action_title="Approve COD / Zero Friction",
            action_description="Low return risk. Process order through standard 1-click checkout.",
            risk_tier="low",
            badge_color="#10b981",  # emerald-500
            recommended_intervention="None — allow instant checkout",
            potential_order_loss=potential_loss,
            expected_savings=expected_savings,
            merchant_notes=[
                "Order is within safe historical boundaries.",
                "Expected reverse logistics loss is negligible.",
            ],
        )

    elif risk_score < 0.50:
        # Dynamic prepaid discount saves full RTO risk if converted
        expected_savings = potential_loss * risk_score * 0.40
        return PolicyAction(
            action_code="NUDGE_PREPAID_UPI",
            action_title="Nudge Prepaid (UPI / Card Discount)",
            action_description="Moderate return risk. Offer instant ₹50 / 5% UPI discount to convert COD into prepaid.",
            risk_tier="moderate",
            badge_color="#3b82f6",  # blue-500
            recommended_intervention="Dynamic UPI Incentive at Magic Checkout",
            potential_order_loss=potential_loss,
            expected_savings=expected_savings,
            merchant_notes=[
                "Converting to prepaid eliminates buyer rejection at doorstep.",
                "Dynamic discount cost is significantly lower than potential RTO freight.",
            ],
        )

    elif risk_score < max(0.65, cost_optimal_threshold):
        # Automated WhatsApp confirmation costs ~₹1-2, saves ~30% of cancellations
        expected_savings = (potential_loss * intervention_success_rate) - intervention_cost
        return PolicyAction(
            action_code="REQUIRE_WHATSAPP_CONFIRMATION",
            action_title="Require Automated Verification",
            action_description="Elevated return risk. Trigger automated WhatsApp/SMS address and intent confirmation.",
            risk_tier="elevated",
            badge_color="#f59e0b",  # amber-500
            recommended_intervention="Automated WhatsApp 2-way verification bot before dispatch",
            potential_order_loss=potential_loss,
            expected_savings=max(0.0, expected_savings),
            merchant_notes=[
                "Verify buyer phone and shipping address before packing.",
                "Orders unconfirmed after 24 hours are automatically reviewed.",
            ],
        )

    else:
        # High risk: Disable COD or require partial prepayment
        expected_savings = (potential_loss * risk_score) - intervention_cost
        return PolicyAction(
            action_code="DISABLE_COD_PREPAID_ONLY",
            action_title="Gate COD (Prepaid Only)",
            action_description="Critical return/cancellation risk. Disable Cash on Delivery or require a prepaid shipping deposit.",
            risk_tier="critical",
            badge_color="#ef4444",  # red-500
            recommended_intervention="Restrict to Online Payment (UPI / Cards / NetBanking)",
            potential_order_loss=potential_loss,
            expected_savings=max(0.0, expected_savings),
            merchant_notes=[
                "High probability of return/refusal at doorstep.",
                "Saves merchant from 2x freight loss and tied-up warehouse inventory.",
            ],
        )
