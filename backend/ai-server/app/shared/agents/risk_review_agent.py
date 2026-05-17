import copy
from typing import Any, Dict, List, Tuple


class RiskReviewAgent:
    """Rule-based user-level risk gate for judge order cards."""

    def review_order(
        self,
        *,
        order_card: Dict[str, Any],
        current_holding: Dict[str, Any],
        quant_state: Dict[str, Any],
        historical_comparison: Dict[str, Any] | None = None,
        signal_confidence: Any = None,
        system_error: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        adjusted = copy.deepcopy(order_card)
        order = adjusted.get("order") if isinstance(adjusted.get("order"), dict) else {}
        risk_management = (
            adjusted.get("risk_management") if isinstance(adjusted.get("risk_management"), dict) else {}
        )

        action = str(order.get("action") or "hold").lower()
        quantity = self._safe_int(order.get("quantity"))
        final_score = self._safe_int(adjusted.get("final_score"))
        reasons: List[str] = []
        risk_score = 0
        quantity_multiplier = 1.0
        historical_comparison = historical_comparison if isinstance(historical_comparison, dict) else {}

        if system_error:
            return self._reject(adjusted, 100, ["upstream system error"])

        if action not in {"buy", "sell"}:
            return self._approve(
                adjusted,
                risk_score=0,
                approved_quantity=0,
                reasons=["no executable order requested"],
            )

        if quantity <= 0:
            return self._reject(adjusted, 90, ["executable order has zero quantity"])

        if action == "sell":
            sellable_quantity = self._safe_int(current_holding.get("available_quantity"))
            if sellable_quantity <= 0:
                return self._reject(adjusted, 95, ["sell requested without available holding"])
            if quantity > sellable_quantity:
                risk_score += 30
                quantity_multiplier = min(quantity_multiplier, sellable_quantity / max(quantity, 1))
                reasons.append("sell quantity exceeds available holding")

        confidence_band = self._confidence_band(signal_confidence)
        if confidence_band == "low":
            risk_score += 25
            quantity_multiplier = min(quantity_multiplier, 0.5)
            reasons.append("signal confidence is low")
        elif confidence_band == "medium":
            risk_score += 10
            quantity_multiplier = min(quantity_multiplier, 0.75)
            reasons.append("signal confidence is medium")

        entry_risk = self._entry_risk(quant_state)
        if entry_risk == "very_high":
            risk_score += 45
            quantity_multiplier = min(quantity_multiplier, 0.25)
            reasons.append("quant entry risk is very high")
        elif entry_risk == "high":
            risk_score += 30
            quantity_multiplier = min(quantity_multiplier, 0.5)
            reasons.append("quant entry risk is high")

        order_type = str(order.get("order_type") or "").lower()
        stop_loss_price = self._safe_int(risk_management.get("stop_loss_price"))
        if action == "buy" and order_type == "market" and stop_loss_price <= 0:
            risk_score += 25
            quantity_multiplier = min(quantity_multiplier, 0.5)
            reasons.append("market buy has no stop loss")

        current_quantity = self._safe_int(current_holding.get("quantity"))
        if action == "buy" and current_quantity > 0:
            risk_score += 15
            quantity_multiplier = min(quantity_multiplier, 0.75)
            reasons.append("additional buy while already holding position")

        if action == "buy" and final_score < 5:
            risk_score += 20
            quantity_multiplier = min(quantity_multiplier, 0.5)
            reasons.append("buy score is weak")
        if action == "sell" and final_score > -5:
            risk_score += 20
            quantity_multiplier = min(quantity_multiplier, 0.5)
            reasons.append("sell score is weak")

        historical_multiplier = self._bounded_float(
            historical_comparison.get("position_size_multiplier"),
            default=1.0,
            minimum=0.0,
            maximum=1.5,
        )
        historical_recommendation = str(historical_comparison.get("recommendation") or "").upper()
        if action == "buy":
            if historical_multiplier < 1.0:
                quantity_multiplier = min(quantity_multiplier, historical_multiplier)
                risk_score += 10
                reasons.append(f"historical comparison caps buy size at {historical_multiplier:.2f}x")
            if historical_recommendation in {"HOLD", "SELL_BIAS"}:
                quantity_multiplier = min(quantity_multiplier, 0.25)
                risk_score += 30
                reasons.append(f"historical comparison recommends {historical_recommendation}")
            elif historical_recommendation == "BUY_LESS":
                quantity_multiplier = min(quantity_multiplier, 0.5)
                risk_score += 15
                reasons.append("historical comparison recommends BUY_LESS")

        risk_score = min(100, risk_score)
        if risk_score >= 80:
            if not reasons:
                reasons.append("risk score exceeded rejection threshold")
            return self._reject(adjusted, risk_score, reasons)

        approved_quantity = quantity
        decision = "APPROVE"
        blocked = False
        if risk_score >= 40 or quantity_multiplier < 1.0:
            decision = "REDUCE_SIZE"
            approved_quantity = max(1, int(quantity * quantity_multiplier))
            adjusted.setdefault("order", {})["quantity"] = approved_quantity

        if not reasons:
            reasons.append("risk checks passed")

        risk_review = {
            "schema": "risk_review_v1",
            "decision": decision,
            "risk_score": risk_score,
            "blocked": blocked,
            "original_quantity": quantity,
            "approved_quantity": approved_quantity,
            "reasons": reasons,
        }
        adjusted["risk_review"] = risk_review
        return adjusted, risk_review

    def _approve(
        self,
        order_card: Dict[str, Any],
        *,
        risk_score: int,
        approved_quantity: int,
        reasons: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        risk_review = {
            "schema": "risk_review_v1",
            "decision": "APPROVE",
            "risk_score": risk_score,
            "blocked": False,
            "original_quantity": approved_quantity,
            "approved_quantity": approved_quantity,
            "reasons": reasons,
        }
        order_card["risk_review"] = risk_review
        return order_card, risk_review

    def _reject(
        self,
        order_card: Dict[str, Any],
        risk_score: int,
        reasons: List[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        original_order = copy.deepcopy(order_card.get("order", {}))
        risk_review = {
            "schema": "risk_review_v1",
            "decision": "REJECT",
            "risk_score": min(100, risk_score),
            "blocked": True,
            "original_quantity": self._safe_int(original_order.get("quantity")),
            "approved_quantity": 0,
            "reasons": reasons,
        }
        order_card["order"] = {
            "action": "hold",
            "order_type": "limit",
            "quantity": 0,
            "price": 0,
            "time_in_force": "day",
        }
        order_card["risk_review"] = risk_review
        order_card["risk_blocked_order"] = original_order
        order_card["adjusted_by_risk_review"] = True
        return order_card, risk_review

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            if isinstance(value, str) and not value.strip():
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
        try:
            if value is None:
                return default
            parsed = float(value)
        except Exception:
            return default
        return max(minimum, min(maximum, parsed))

    @staticmethod
    def _confidence_band(value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"high", "medium", "low"}:
                return normalized
        try:
            confidence = float(value)
        except Exception:
            return "medium"
        if confidence < 0.5:
            return "low"
        if confidence < 0.75:
            return "medium"
        return "high"

    @classmethod
    def _entry_risk(cls, quant_state: Dict[str, Any]) -> str:
        risk_context = quant_state.get("risk_context") if isinstance(quant_state, dict) else {}
        if not isinstance(risk_context, dict):
            return "unknown"
        raw_risk = risk_context.get("entry_risk")
        if isinstance(raw_risk, str):
            normalized = raw_risk.strip().lower()
            if normalized in {"very_high", "high", "medium", "low"}:
                return normalized
        try:
            risk_value = float(raw_risk)
        except Exception:
            return "unknown"
        if risk_value >= 0.85:
            return "very_high"
        if risk_value >= 0.7:
            return "high"
        if risk_value >= 0.45:
            return "medium"
        return "low"
