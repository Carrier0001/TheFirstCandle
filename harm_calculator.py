from dataclasses import dataclass
from enum import Enum
from typing import List, Dict

# =========================
# ENUMS
# =========================

class Status(Enum):
    ACCRUING = "ACCRUING"
    STABILIZED = "STABILIZED"
    REPAIRED = "REPAIRED"
    UNREPAIRED = "UNREPAIRED"

class Confidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class HarmType(Enum):
    NEGLIGENCE = 1.0
    RECKLESSNESS = 2.0
    DELIBERATE = 5.0
    SYSTEMIC = 8.0
    COVER_UP = 10.0

# =========================
# ENTRIES (APPEND-ONLY)
# =========================

@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    entity_id: str
    year: int
    date_logged: str = ""   # ✅ Added back
    harm_ly: float = 0.0
    harm_ecy: float = 0.0
    surplus_ly: float = 0.0
    surplus_ecy: float = 0.0
    description: str = ""
    harm_type: str = "NEGLIGENCE"
    confidence: Confidence = Confidence.MEDIUM
    source_hash: str = ""
    age_adjustment_note: str = ""

    def __post_init__(self):
        if self.harm_ly > 0 or self.harm_ecy > 0:
            raise ValueError("Harm must be ≤ 0")
        if self.surplus_ly < 0 or self.surplus_ecy < 0:
            raise ValueError("Surplus must be ≥ 0")

    def intent_multiplier(self) -> float:
        return HarmType[self.harm_type].value if self.harm_type in HarmType.__members__ else 1.0

    def amplified_harm(self) -> Dict[str, float]:
        mult = self.intent_multiplier()
        return {
            "harm_ly": self.harm_ly * mult,
            "harm_ecy": self.harm_ecy * mult
        }

# =========================
# CALCULATED VIEWS (READ-ONLY)
# =========================

@dataclass
class AnnualView:
    year: int
    harm_ly: float
    harm_ecy: float
    surplus_ly: float
    surplus_ecy: float
    status: Status

@dataclass
class LifetimeView:
    harm_ly: float
    harm_ecy: float
    surplus_ly: float
    surplus_ecy: float
    outstanding_ly: float
    outstanding_ecy: float
    status: Status

# =========================
# CALCULATOR
# =========================

class LedgerCalculator:
    """
    This calculator NEVER mutates data.
    It summarizes JSON that is already authoritative.
    """

    @staticmethod
    def historical_balance(entity_id: str, entries: List[LedgerEntry]) -> LifetimeView:
        harm_ly = sum(e.amplified_harm()["harm_ly"] for e in entries)
        harm_ecy = sum(e.amplified_harm()["harm_ecy"] for e in entries)
        surplus_ly = sum(e.surplus_ly for e in entries)
        surplus_ecy = sum(e.surplus_ecy for e in entries)

        outstanding_ly = harm_ly + surplus_ly
        outstanding_ecy = harm_ecy + surplus_ecy

        if outstanding_ly >= 0 and outstanding_ecy >= 0:
            status = Status.REPAIRED
        elif surplus_ly > 0 or surplus_ecy > 0:
            status = Status.STABILIZED
        elif harm_ly < 0 or harm_ecy < 0:
            status = Status.ACCRUING
        else:
            status = Status.UNREPAIRED

        return LifetimeView(
            harm_ly=harm_ly,
            harm_ecy=harm_ecy,
            surplus_ly=surplus_ly,
            surplus_ecy=surplus_ecy,
            outstanding_ly=outstanding_ly,
            outstanding_ecy=outstanding_ecy,
            status=status
        )

    @staticmethod
    def calculate_annual_view(entity: dict, entries: List[LedgerEntry], year: int) -> AnnualView:
        relevant = [e for e in entries if e.year == year]

        harm_ly = sum(e.amplified_harm()["harm_ly"] for e in relevant)
        harm_ecy = sum(e.amplified_harm()["harm_ecy"] for e in relevant)
        surplus_ly = sum(e.surplus_ly for e in relevant)
        surplus_ecy = sum(e.surplus_ecy for e in relevant)

        if harm_ly < 0 or harm_ecy < 0:
            status = Status.ACCRUING
        elif surplus_ly > 0 or surplus_ecy > 0:
            status = Status.STABILIZED
        else:
            status = Status.REPAIRED

        return AnnualView(
            year=year,
            harm_ly=harm_ly,
            harm_ecy=harm_ecy,
            surplus_ly=surplus_ly,
            surplus_ecy=surplus_ecy,
            status=status
        )

    @staticmethod
    def lifetime_view(entity: dict) -> LifetimeView:
        """
        Lifetime values are READ from JSON.
        They are never recomputed.
        """
        lt = entity["lifetime"]

        status = (
            Status.REPAIRED
            if lt["outstanding_ly"] == 0 and lt["outstanding_ecy"] == 0
            else Status.UNREPAIRED
        )

        return LifetimeView(
            harm_ly=lt["harm_ly"],
            harm_ecy=lt["harm_ecy"],
            surplus_ly=lt["surplus_ly"],
            surplus_ecy=lt["surplus_ecy"],
            outstanding_ly=lt["outstanding_ly"],
            outstanding_ecy=lt["outstanding_ecy"],
            status=status
        )

    @staticmethod
    def harm_breakdown(entries: List[LedgerEntry]) -> Dict[str, Dict[str, float]]:
        breakdown: Dict[str, Dict[str, float]] = {}
        for e in entries:
            if e.harm_ly < 0 or e.harm_ecy < 0:
                mult = e.intent_multiplier()
                key = e.harm_type
                if key not in breakdown:
                    breakdown[key] = {"ly": 0.0, "ecy": 0.0, "count": 0}
                breakdown[key]["ly"] += e.harm_ly * mult
                breakdown[key]["ecy"] += e.harm_ecy * mult
                breakdown[key]["count"] += 1
        return breakdown

# =========================
# FORMATTERS
# =========================

def format_ly(value: float) -> str:
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val < 1_000:
        return f"{sign}{abs_val:,.0f}"
    elif abs_val < 1_000_000:
        return f"{sign}{abs_val / 1_000:,.1f}K"
    elif abs_val < 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000:,.1f}M"
    elif abs_val < 1_000_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:,.2f}B"
    else:
        return f"{sign}{abs_val / 1_000_000_000_000:,.2f}T"
