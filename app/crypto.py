import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)

# --- Core Cryptographic Functions ---

def generate_private_key():
    """Generates a new ECDSA private key."""
    return ec.generate_private_key(ec.SECP256K1())

def get_public_key(private_key):
    """Derives the public key from a private key."""
    return private_key.public_key()

def sign_message(private_key, message: bytes) -> bytes:
    """Signs a message (hash) with the private key."""
    return private_key.sign(message, ec.ECDSA(hashes.SHA256()))

def verify_signature(public_key, signature: bytes, message: bytes) -> bool:
    """Verifies a signature against the public key and original message."""
    try:
        public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

def sha256_hash(data: bytes) -> str:
    """Computes the SHA-256 hash of the given data and returns it as a hex string."""
    return hashlib.sha256(data).hexdigest()

# --- Serialization and Address Functions ---

def serialize_public_key(public_key) -> str:
    """Serializes a public key to a Base64 string for storage/transmission."""
    return base64.b64encode(
        public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        )
    ).decode('utf-8')

def serialize_private_key(private_key) -> str:
    """Serializes a private key to a Base64 string."""
    return base64.b64encode(
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )
    ).decode('utf-8')

def generate_address(public_key) -> str:
    """
    Generates a P2PKH-style address from a public key.
    This is a simplified version of the Bitcoin process (hash160, base58check).
    Here: address = 'addr_' + sha256(serialized_public_key)[:30]
    """
    serialized_key = serialize_public_key(public_key).encode('utf-8')
    return f"addr_{sha256_hash(serialized_key)[:30]}"


# --- P2PKH Scripting Simulation ---

def create_script_pub_key(address: str) -> str:
    """
    Creates a simplified locking script for P2PKH.
    Format: "OP_DUP OP_HASH160 <address> OP_EQUALVERIFY OP_CHECKSIG"
    """
    return f"OP_DUP OP_HASH160 {address} OP_EQUALVERIFY OP_CHECKSIG"

def create_script_sig(signature_b64: str, public_key_b64: str) -> str:
    """
    Creates a simplified unlocking script for P2PKH.
    Format: "<signature_base64> <public_key_base64>"
    """
    return f"{signature_b64} {public_key_b64}"

def execute_script(script_sig: str, script_pub_key: str, transaction_hash: str) -> bool:
    """
    Simulates the execution of the Bitcoin scripting system for P2PKH.
    It verifies that the public key hashes to the address and that the signature is valid.
    """
    # 1. Deconstruct scripts
    try:
        sig_b64, pub_key_b64 = script_sig.split(' ')

        parts = script_pub_key.split(' ')
        # Expected format: "OP_DUP OP_HASH160 <address> OP_EQUALVERIFY OP_CHECKSIG"
        if len(parts) != 5 or parts[0] != "OP_DUP" or parts[1] != "OP_HASH160":
             return False
        address_from_script = parts[2]
    except ValueError:
        return False # Invalid script format

    # 2. Verify that the public key matches the address in the locking script
    # (This is the "HASH160" and "EQUALVERIFY" part)
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    public_key_bytes = base64.b64decode(pub_key_b64)
    public_key = load_pem_public_key(public_key_bytes)

    derived_address = generate_address(public_key)
    if derived_address != address_from_script:
        return False

    # 3. Verify the signature ("CHECKSIG" part)
    signature_bytes = base64.b64decode(sig_b64)
    message_bytes = transaction_hash.encode('utf-8')

    return verify_signature(public_key, signature_bytes, message_bytes)
