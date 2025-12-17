from typing import Dict, Any

REQUIRED_LIFETIME_FIELDS = {
    "harm_ly",
    "harm_ecy",
    "surplus_ly",
    "surplus_ecy",
    "outstanding_ly",
    "outstanding_ecy",
    "status"
}

REQUIRED_CURRENT_YEAR_FIELDS = {
    "year",
    "harm_ly",
    "harm_ecy",
    "surplus_ly",
    "surplus_ecy",
    "status"
}

def validate_entity_schema(entity: Dict[str, Any]) -> None:
    """
    Raises ValueError if schema is invalid.
    This is a hard gate — no silent fixes.
    """

    if "entity_id" not in entity:
        raise ValueError("Missing entity_id")

    if "entity_state" not in entity:
        raise ValueError("Missing entity_state")

    if "lifetime" not in entity:
        raise ValueError("Missing lifetime block")

    lifetime = entity["lifetime"]
    missing = REQUIRED_LIFETIME_FIELDS - lifetime.keys()
    if missing:
        raise ValueError(f"Lifetime missing fields: {missing}")

    # Active entities must have current_year
    if entity["entity_state"] == "ACTIVE":
        if "current_year" not in entity:
            raise ValueError("ACTIVE entity missing current_year")

        cy = entity["current_year"]
        missing = REQUIRED_CURRENT_YEAR_FIELDS - cy.keys()
        if missing:
            raise ValueError(f"Current year missing fields: {missing}")

    # Entries must exist (even if empty)
    if "entries" not in entity or not isinstance(entity["entries"], list):
        raise ValueError("entries must be a list")

    # Hard numeric sanity checks
    if lifetime["harm_ly"] > 0 or lifetime["harm_ecy"] > 0:
        raise ValueError("Lifetime harm must be ≤ 0")

    if lifetime["surplus_ly"] < 0 or lifetime["surplus_ecy"] < 0:
        raise ValueError("Lifetime surplus must be ≥ 0")