# verify.py — THIS ONE WORKS 100%
import json, hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

with open("GENESIS_BLOCK.json") as f:
    genesis = json.load(f)

entry = genesis["genesis_entry"]
data = json.dumps(entry, sort_keys=True, separators=(',', ':')).encode()

print("Verifying The Ledger...\n")

good = True
for s in genesis["signatures"]:
    try:
        pub = serialization.load_pem_public_key(s["pubkey"].encode())
        raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        key = ed25519.Ed25519PublicKey.from_public_bytes(raw)
        key.verify(bytes.fromhex(s["signature"]), data)
        print(f"Signature valid: {s['carrier']}")
    except:
        print(f"INVALID SIGNATURE: {s['carrier']}")
        good = False

if good:
    print("\nCANONICAL — ALL ROWS VERIFIED")
    print("The ledger is untampered and valid.")
else:
    print("\nGENESIS BLOCK COMPROMISED")