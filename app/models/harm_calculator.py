from typing import Dict, Any, List, Optional
from app.models.enums import HarmType

class HarmCalculator:
    INTENT_MULTIPLIERS = {
        HarmType.NEGLIGENCE: 1.0,
        HarmType.RECKLESSNESS: 1.8,
        HarmType.DELIBERATE: 3.0,
        HarmType.SYSTEMIC: 4.5,
        HarmType.COVER_UP: 10.0,
    }

    @staticmethod
    def calculate_harm(
        life_loss: int,
        financial_loss: float,
        ecosystem_loss: Optional[float],
        num_affected: int,
        victim_ages: List[Optional[int]],
        intent_type: HarmType
    ) -> Dict[str, Any]:
        multiplier = HarmCalculator.INTENT_MULTIPLIERS.get(intent_type, 1.0)

        if victim_ages and any(a is not None for a in victim_ages):
            valid = [a for a in victim_ages if a is not None and 0 <= a <= 130]
            avg_age = sum(valid) / len(valid) if valid else 45
            ly_per_person = max(85 - avg_age, 0)
        else:
            ly_per_person = 40

        harm_ly = -(ly_per_person * num_affected * multiplier)
        harm_financial = -(financial_loss * multiplier)
        harm_ecosystem = -(ecosystem_loss or 0) * multiplier

        severity = min(100, (
            (abs(harm_ly) / 1000) * 0.4 +
            (abs(harm_financial) / 1000000) * 0.4 +
            (abs(harm_ecosystem) / 1000) * 0.2
        ) * 100)

        return {
            "harm_ly": round(harm_ly, 2),
            "financial_usd": round(harm_financial, 2),
            "harm_ecy": round(harm_ecosystem, 2),
            "intent_multiplier": multiplier,
            "severity_score": round(severity, 1)
        }

    @staticmethod
    def update_confidence(total_affected: int) -> str:
        if total_affected >= 10000:
            return "CERTAINTY"
        elif total_affected >= 1000:
            return "HIGH"
        elif total_affected >= 100:
            return "MEDIUM"
        return "LOW"