from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import os
import sqlite3
from datetime import datetime

def generate_carrier_keys(carrier_name):
    """Generate Ed25519 key pair and save to files"""
    
    print(f"\nGenerating keys for {carrier_name}...")
    
    # Generate Ed25519 key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize private key (PEM format)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key (PEM format)
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Create keys directory if it doesn't exist
    os.makedirs('keys', exist_ok=True)
    
    # Save private key (KEEP SECRET)
    private_file = f'keys/{carrier_name}_private.pem'
    with open(private_file, 'wb') as f:
        f.write(private_pem)
    
    # Save public key (PUBLIC)
    public_file = f'keys/{carrier_name}_public.pem'
    with open(public_file, 'wb') as f:
        f.write(public_pem)
    
    print(f"✓ Keys generated")
    print(f"  Private key: {private_file} (🔒 KEEP SECRET)")
    print(f"  Public key:  {public_file}")
    
    return public_pem.decode(), private_file, public_file

def register_carrier(carrier_name, pubkey):
    """Add carrier to the database"""
    
    conn = sqlite3.connect('ledger.db')
    c = conn.cursor()
    
    date_joined = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''
        INSERT OR IGNORE INTO carriers (pubkey, carrier_name, date_joined, status, tier)
        VALUES (?, ?, ?, 'Active', 'Full')
    ''', (pubkey, carrier_name, date_joined))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Registered in database")

if __name__ == "__main__":
    print("="*80)
    print("GENERATING CARRIER KEYS FOR GENESIS BLOCK")
    print("="*80)
    
    # Generate keys for first three carriers
    carriers = ["carrier_1", "carrier_2", "carrier_3"]
    
    for carrier in carriers:
        pubkey, private_file, public_file = generate_carrier_keys(carrier)
        register_carrier(carrier, pubkey)
        
        print(f"\n⚠️  CRITICAL: BACKUP {carrier}'s PRIVATE KEY")
        print(f"   - Write down on paper")
        print(f"   - Save to encrypted USB")
        print(f"   - Store in hardware wallet")
        print("-" * 80)
    
    print("\n" + "="*80)
    print("✓ ALL CARRIER KEYS GENERATED")
    print("="*80)
    print("\nNext step: Run sign_genesis.py to create the genesis block")