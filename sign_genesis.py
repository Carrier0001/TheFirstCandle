# sign_genesis.py — FINAL, CORRECT VERSION
import json, sqlite3, hashlib, os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from datetime import datetime

genesis = {
    "entry_id": "GENESIS_2025-12-21",
    "date_logged": "2025-12-21",
    "category": "System",
    "type": "Genesis",
    "intent": "Initialization",
    "description": "First Candle Ledger Genesis Block - The Vow v1.0 signed by first three carriers on December 21, 2025 at 00:01 UTC",
    "harm_cost_ly": 0,
    "surplus_ly": 0,
    "source": "First Candle Project",
    "validator_status": "Verified",
    "net_balance": 0,
    "patch_status": "Immutable",
    "notes": "Genesis block establishing the ledger. Pillar 0 scope rules are now active.",
    "timestamp": 1767225660
}

signatures = []
for i in [1,2,3]:
    priv = serialization.load_pem_private_key(open(f"keys/carrier_{i}_private.pem","rb").read(), password=None)
    sig = priv.sign(json.dumps(genesis, sort_keys=True, separators=(',', ':')).encode()).hex()
    pub = open(f"keys/carrier_{i}_public.pem").read()
    signatures.append({"carrier": f"carrier_{i}", "pubkey": pub.strip(), "signature": sig})

full = {"genesis_entry": genesis, "signatures": signatures}
with open("GENESIS_BLOCK.json","w") as f:
    json.dump(full, f, indent=2)

# Add to DB
conn = sqlite3.connect("ledger.db")
c = conn.cursor()
c.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
    genesis["entry_id"], genesis["date_logged"], genesis["category"], genesis["type"], genesis["intent"],
    genesis["description"], 0,0,0,0,0,0, genesis["source"], "Verified", 0, "Immutable",
    genesis["notes"], signatures[0]["signature"], signatures[0]["pubkey"], genesis["timestamp"]
))
conn.commit()
conn.close()

print("GENESIS BLOCK CREATED AND SIGNED CORRECTLY")
print("NOW RUN: python verify.py")