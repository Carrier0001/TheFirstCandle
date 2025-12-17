import json
import os

from harm_calculator import (
    LedgerEntry,
    LedgerCalculator,
    format_ly
)

from schema_validator import validate_entity_schema
from lifetime_signature import verify_lifetime

DATA_FOLDER = "data"


def load_entity(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        entity = json.load(f)

    # HARD GATES — NO SILENT FAILURES
    validate_entity_schema(entity)
    verify_lifetime(entity)

    return entity


def load_entries(entity: dict):
    entries = []
    for raw in entity.get("entries", []):
        entries.append(LedgerEntry(
            entry_id=raw["entry_id"],
            entity_id=entity["entity_id"],
            date_logged=raw.get("date_logged", ""),
            year=raw["year"],
            harm_ly=raw.get("harm_ly", 0.0),
            harm_ecy=raw.get("harm_ecy", 0.0),
            surplus_ly=raw.get("surplus_ly", 0.0),
            surplus_ecy=raw.get("surplus_ecy", 0.0),
            description=raw.get("description", ""),
            harm_type=raw.get("harm_type", "NEGLIGENCE"),
        ))
    return entries


def main():
    files = sorted(f for f in os.listdir(DATA_FOLDER) if f.endswith(".json"))

    for filename in files:
        path = os.path.join(DATA_FOLDER, filename)

        print(f"\n{'='*78}")
        print(f"ENTITY FILE: {filename}")
        print(f"{'='*78}")

        try:
            entity = load_entity(path)
            entries = load_entries(entity)

            entity_id = entity["entity_id"]
            state = entity["entity_state"]

            # -------------------------------
            # 📜 LIFETIME (ALWAYS SHOWN)
            # -------------------------------
            lifetime = entity["lifetime"]

            print("\n📜 LIFETIME LEDGER (Eternal Memory)")
            print(f"  Harm LY:        {format_ly(lifetime['harm_ly'])}")
            print(f"  Harm ECY:       {format_ly(lifetime['harm_ecy'])}")
            print(f"  Surplus LY:     {format_ly(lifetime['surplus_ly'])}")
            print(f"  Surplus ECY:    {format_ly(lifetime['surplus_ecy'])}")
            print(f"  Outstanding LY:{format_ly(lifetime['outstanding_ly'])}")
            print(f"  Outstanding ECY:{format_ly(lifetime['outstanding_ecy'])}")
            print(f"  Status:         {lifetime['status']}")

            # -------------------------------
            # 📅 CURRENT YEAR (ACTIVE ONLY)
            # -------------------------------
            if state == "ACTIVE":
                cy = entity["current_year"]
                year = cy["year"]

                print(f"\n📅 CURRENT YEAR ({year})")
                print(f"  Harm LY:        {format_ly(cy['harm_ly'])}")
                print(f"  Harm ECY:       {format_ly(cy['harm_ecy'])}")
                print(f"  Surplus LY:     {format_ly(cy['surplus_ly'])}")
                print(f"  Surplus ECY:    {format_ly(cy['surplus_ecy'])}")
                print(f"  Status:         {cy['status']}")

            else:
                print("\n⏛ HISTORICAL ENTITY — No current-year accountability")

            # -------------------------------
            # ⚖️ EVIDENCE BREAKDOWN
            # -------------------------------
            if entries:
                print("\n⚖️ HARM BREAKDOWN (By Intent Type)")
                breakdown = {}

                for e in entries:
                    if e.harm_ly < 0 or e.harm_ecy < 0:
                        m = e.get_intent_multiplier()
                        key = e.harm_type
                        if key not in breakdown:
                            breakdown[key] = {"ly": 0, "ecy": 0, "count": 0}
                        breakdown[key]["ly"] += e.harm_ly * m
                        breakdown[key]["ecy"] += e.harm_ecy * m
                        breakdown[key]["count"] += 1

                for k, v in sorted(breakdown.items()):
                    print(
                        f"  {k:12} "
                        f"({v['count']:>3}): "
                        f"{format_ly(v['ly']):>12} LY | "
                        f"{format_ly(v['ecy']):>12} ECY"
                    )
            else:
                print("\n(No entries yet)")

        except Exception as e:
            print(f"❌ ERROR: {e}")

    print(f"\n{'='*78}")
    print("✅ ALL ENTITIES PROCESSED — NO RECOMPUTATION, NO ZEROING")
    print(f"{'='*78}\n")


if __name__ == "__main__":
    main()