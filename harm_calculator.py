from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional

# =========================
# ENUMS
# =========================

class Status(Enum):
    ACCRUING = "ACCRUING"        # Active harm, no repair
    STABILIZED = "STABILIZED"    # Some repair, but outstanding debt remains
    REPAIRED = "REPAIRED"        # Debt fully offset by surplus

class Confidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class HarmType(Enum):
    """Intent multipliers - how deliberate was the harm?"""
    NEGLIGENCE = 1.0      # Failed to prevent
    RECKLESSNESS = 2.0    # Knew risk, did it anyway
    DELIBERATE = 5.0      # Intended the harm
    SYSTEMIC = 8.0        # Built into policy/structure
    COVER_UP = 10.0       # Denied, suppressed, or concealed harm

class IncidentType(Enum):
    """Causation categories"""
    DIRECT_VIOLENCE = "DIRECT_VIOLENCE"           # Shooting, execution, assault
    NEGLIGENCE = "NEGLIGENCE"                     # Preventable death from inaction
    SYSTEMIC_POLICY = "SYSTEMIC_POLICY"           # Death from institutional policy
    ENVIRONMENTAL = "ENVIRONMENTAL"               # Pollution, ecosystem destruction
    MEDICAL_DENIAL = "MEDICAL_DENIAL"             # Denied care, treatment, coverage
    LEGAL_SUPPRESSION = "LEGAL_SUPPRESSION"       # Lawsuit to suppress accountability
    INTIMIDATION = "INTIMIDATION"                 # Threats against witnesses/victims

# =========================
# LEDGER ENTRY (IMMUTABLE)
# =========================

@dataclass(frozen=True)
class LedgerEntry:
    """
    A single entry in the accountability ledger.
    Once created, CANNOT be modified. Append-only.
    """
    entry_id: str                           # Unique identifier
    entity_id: str                          # Which institution is being measured
    year: int                               # Year harm occurred
    date_logged: str                        # ISO format: 2025-12-26T14:30:00Z
    
    # HARM (always negative or zero)
    harm_ly: float = 0.0                    # Life-Years lost
    harm_ecy: float = 0.0                   # Ecosystem-Capacity-Years lost
    
    # SURPLUS (always positive or zero) 
    surplus_ly: float = 0.0                 # Life-Years saved/restored
    surplus_ecy: float = 0.0                # Ecosystem-Capacity restored
    
    # CAUSATION
    incident_type: str = "NEGLIGENCE"       # From IncidentType enum
    causation_evidence: str = ""            # Brief description of causal link
    
    # VICTIMS
    num_affected: int = 0                   # Number of people/entities harmed
    avg_age_at_harm: float = 0.0           # For LY calculations
    
    # INTENT (determines multiplier)
    harm_type: str = "NEGLIGENCE"          # From HarmType enum
    
    # METADATA
    confidence: Confidence = Confidence.MEDIUM
    source_hash: str = ""                   # Cryptographic hash of testimony
    description: str = ""                   # Human-readable summary
    response_to_entry_id: str = ""         # If this is institutional response

    def __post_init__(self):
        """Validate entry integrity"""
        if self.harm_ly > 0 or self.harm_ecy > 0:
            raise ValueError("Harm must be ≤ 0 (negative or zero)")
        if self.surplus_ly < 0 or self.surplus_ecy < 0:
            raise ValueError("Surplus must be ≥ 0 (positive or zero)")

    def intent_multiplier(self) -> float:
        """Get the multiplier for this harm based on institutional intent"""
        try:
            return HarmType[self.harm_type].value
        except KeyError:
            return 1.0  # Default to NEGLIGENCE if invalid

    def amplified_harm(self) -> Dict[str, float]:
        """Return harm with intent multiplier applied"""
        mult = self.intent_multiplier()
        return {
            "harm_ly": self.harm_ly * mult,
            "harm_ecy": self.harm_ecy * mult
        }

# =========================
# CALCULATED VIEWS
# =========================

@dataclass
class AnnualView:
    """Snapshot of one year's activity"""
    year: int
    harm_ly: float
    harm_ecy: float
    surplus_ly: float
    surplus_ecy: float
    outstanding_ly: float
    outstanding_ecy: float
    status: Status

@dataclass
class LifetimeView:
    """Entire institutional history"""
    harm_ly: float              # Total amplified harm
    harm_ecy: float
    surplus_ly: float           # Total repair
    surplus_ecy: float
    outstanding_ly: float       # harm + surplus (negative = debt)
    outstanding_ecy: float
    status: Status
    years_to_repair: Optional[float] = None  # At current surplus rate

# =========================
# CALCULATOR (READ-ONLY)
# =========================

class LedgerCalculator:
    """
    This calculator NEVER modifies data.
    It only reads and summarizes the ledger.
    """

    @staticmethod
    def calculate_annual_view(entries: List[LedgerEntry], year: int) -> AnnualView:
        """Calculate one year's balance"""
        relevant = [e for e in entries if e.year == year]

        harm_ly = sum(e.amplified_harm()["harm_ly"] for e in relevant)
        harm_ecy = sum(e.amplified_harm()["harm_ecy"] for e in relevant)
        surplus_ly = sum(e.surplus_ly for e in relevant)
        surplus_ecy = sum(e.surplus_ecy for e in relevant)
        
        outstanding_ly = harm_ly + surplus_ly
        outstanding_ecy = harm_ecy + surplus_ecy

        # Determine status
        if outstanding_ly >= 0 and outstanding_ecy >= 0:
            status = Status.REPAIRED
        elif surplus_ly > 0 or surplus_ecy > 0:
            status = Status.STABILIZED
        else:
            status = Status.ACCRUING

        return AnnualView(
            year=year,
            harm_ly=harm_ly,
            harm_ecy=harm_ecy,
            surplus_ly=surplus_ly,
            surplus_ecy=surplus_ecy,
            outstanding_ly=outstanding_ly,
            outstanding_ecy=outstanding_ecy,
            status=status
        )

    @staticmethod
    def calculate_lifetime_view(entries: List[LedgerEntry]) -> LifetimeView:
        """Calculate entire institutional history"""
        harm_ly = sum(e.amplified_harm()["harm_ly"] for e in entries)
        harm_ecy = sum(e.amplified_harm()["harm_ecy"] for e in entries)
        surplus_ly = sum(e.surplus_ly for e in entries)
        surplus_ecy = sum(e.surplus_ecy for e in entries)

        outstanding_ly = harm_ly + surplus_ly
        outstanding_ecy = harm_ecy + surplus_ecy

        # Determine status
        if outstanding_ly >= 0 and outstanding_ecy >= 0:
            status = Status.REPAIRED
        elif surplus_ly > 0 or surplus_ecy > 0:
            status = Status.STABILIZED
        else:
            status = Status.ACCRUING
        
        # Calculate years to repair at current rate
        years_to_repair = None
        if outstanding_ly < 0 and surplus_ly > 0:
            # Get recent surplus rate (last 5 years average)
            recent_entries = sorted(entries, key=lambda e: e.year, reverse=True)[:100]
            recent_surplus = sum(e.surplus_ly for e in recent_entries if e.surplus_ly > 0)
            recent_years = len(set(e.year for e in recent_entries))
            if recent_years > 0 and recent_surplus > 0:
                avg_annual_surplus = recent_surplus / recent_years
                years_to_repair = abs(outstanding_ly) / avg_annual_surplus

        return LifetimeView(
            harm_ly=harm_ly,
            harm_ecy=harm_ecy,
            surplus_ly=surplus_ly,
            surplus_ecy=surplus_ecy,
            outstanding_ly=outstanding_ly,
            outstanding_ecy=outstanding_ecy,
            status=status,
            years_to_repair=years_to_repair
        )

    @staticmethod
    def harm_breakdown(entries: List[LedgerEntry]) -> Dict[str, Dict[str, float]]:
        """Break down harm by type (NEGLIGENCE, DELIBERATE, COVER_UP, etc.)"""
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

    @staticmethod
    def response_chain(entries: List[LedgerEntry], original_entry_id: str) -> List[LedgerEntry]:
        """Track institutional responses to a specific harm"""
        return [e for e in entries if e.response_to_entry_id == original_entry_id]

# =========================
# FORMATTERS
# =========================

def format_ly(value: float) -> str:
    """Format Life-Years for human readability"""
    abs_val = abs(value)
    sign = "-" if value < 0 else "+"
    
    if abs_val == 0:
        return "0"
    elif abs_val < 1_000:
        return f"{sign}{abs_val:,.0f}"
    elif abs_val < 1_000_000:
        return f"{sign}{abs_val / 1_000:,.1f}K"
    elif abs_val < 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000:,.1f}M"
    elif abs_val < 1_000_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:,.2f}B"
    else:
        return f"{sign}{abs_val / 1_000_000_000_000:,.2f}T"

def format_years_to_repair(years: Optional[float]) -> str:
    """Format time-to-repair estimate"""
    if years is None:
        return "Cannot repair (no surplus activity)"
    elif years < 1:
        return f"{years * 12:.0f} months"
    elif years < 100:
        return f"{years:.0f} years"
    elif years < 1000:
        return f"{years:.0f} years (multiple generations)"
    else:
        return f"{years:.0f} years (effectively permanent)"

# =========================
# LIFE EXPECTANCY DATA
# =========================

# Simplified - production version would use WHO database
LIFE_EXPECTANCY_TABLE = {
    (2025, "GLOBAL"): 73.0,
    (2025, "USA"): 78.5,
    (2025, "NIGERIA"): 54.0,
    (2025, "JAPAN"): 84.5,
    (2020, "GLOBAL"): 72.0,
    (2000, "GLOBAL"): 67.0,
    (1980, "GLOBAL"): 63.0,
    (1950, "GLOBAL"): 48.0,
}

def get_life_expectancy(year: int, country: str = "GLOBAL") -> float:
    """Get life expectancy for a given year and country"""
    return LIFE_EXPECTANCY_TABLE.get((year, country), 70.0)

def calculate_life_years_lost(age_at_death: int, year: int, country: str = "GLOBAL") -> float:
    """
    Calculate Life-Years lost from a death.
    Only counts institutional harm, not natural death.
    """
    life_expectancy = get_life_expectancy(year, country)
    remaining = max(0, life_expectancy - age_at_death)
    return -remaining  # Negative because it's harm

# =========================
# EXAMPLE USAGE
# =========================

if __name__ == "__main__":
    # Example: Police department with shooting and cover-up
    entries = [
        LedgerEntry(
            entry_id="PD_2023_001",
            entity_id="POLICE_DEPT_X",
            year=2023,
            date_logged="2023-06-15T14:30:00Z",
            harm_ly=-53.0,  # 25-year-old killed (78-25=53)
            incident_type="DIRECT_VIOLENCE",
            causation_evidence="Officer-involved shooting, unarmed victim",
            num_affected=1,
            avg_age_at_harm=25.0,
            harm_type="DELIBERATE",
            confidence=Confidence.HIGH,
            description="Unarmed civilian killed during traffic stop"
        ),
        LedgerEntry(
            entry_id="PD_2023_002",
            entity_id="POLICE_DEPT_X",
            year=2023,
            date_logged="2023-06-20T09:15:00Z",
            harm_ly=-53.0,  # Same death, but measuring the cover-up
            incident_type="LEGAL_SUPPRESSION",
            causation_evidence="Department issued false statement claiming victim was armed",
            harm_type="COVER_UP",
            confidence=Confidence.HIGH,
            description="False official statement about shooting",
            response_to_entry_id="PD_2023_001"
        ),
        LedgerEntry(
            entry_id="PD_2024_001",
            entity_id="POLICE_DEPT_X",
            year=2024,
            date_logged="2024-03-10T11:00:00Z",
            surplus_ly=5.0,
            incident_type="SYSTEMIC_POLICY",
            description="Reformed use-of-force policy, estimated 5 LY saved annually",
            confidence=Confidence.MEDIUM
        )
    ]
    
    calc = LedgerCalculator()
    lifetime = calc.calculate_lifetime_view(entries)
    
    print(f"Lifetime View for POLICE_DEPT_X:")
    print(f"  Harm: {format_ly(lifetime.harm_ly)}")
    print(f"  Surplus: {format_ly(lifetime.surplus_ly)}")
    print(f"  Outstanding: {format_ly(lifetime.outstanding_ly)}")
    print(f"  Status: {lifetime.status.value}")
    print(f"  Time to repair: {format_years_to_repair(lifetime.years_to_repair)}")
    
    breakdown = calc.harm_breakdown(entries)
    print(f"\nHarm Breakdown:")
    for harm_type, values in breakdown.items():
        print(f"  {harm_type}: {format_ly(values['ly'])} ({values['count']} entries)")
