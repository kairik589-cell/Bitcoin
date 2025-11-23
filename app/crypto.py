import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
    load_pem_public_key
)
from typing import List

# --- Core Cryptographic Functions ---

def generate_private_key():
    return ec.generate_private_key(ec.SECP256K1())

def get_public_key(private_key):
    return private_key.public_key()

def sign_message(private_key, message: bytes) -> bytes:
    return private_key.sign(message, ec.ECDSA(hashes.SHA256()))

def verify_signature(public_key, signature: bytes, message: bytes) -> bool:
    try:
        public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

def sha256_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# --- Serialization and Address Functions ---

def serialize_public_key(public_key) -> str:
    return base64.b64encode(
        public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        )
    ).decode('utf-8')

def serialize_private_key(private_key) -> str:
    return base64.b64encode(
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )
    ).decode('utf-8')

def generate_p2pkh_address(public_key) -> str:
    """Generates a standard Pay-to-Public-Key-Hash address."""
    serialized_key = serialize_public_key(public_key).encode('utf-8')
    return f"addr_{sha256_hash(serialized_key)[:30]}"

# --- Scripting System ---

def create_p2pkh_locking_script(address: str) -> str:
    """Format: P2PKH <address>"""
    return f"P2PKH {address}"

def create_p2pkh_unlocking_script(signature_b64: str, public_key_b64: str) -> str:
    """Format: <signature_b64> <public_key_b64>"""
    return f"{signature_b64} {public_key_b64}"

def execute_script(unlocking_script: str, locking_script: str, transaction_hash: str) -> bool:
    """
    Simulates the execution of the P2PKH script.
    """
    script_type, address_from_lock = locking_script.split(' ', 1)

    if script_type != "P2PKH":
        return False

    try:
        sig_b64, pub_key_b64 = unlocking_script.split(' ')
    except ValueError: return False

    public_key = load_pem_public_key(base64.b64decode(pub_key_b64))

    # Verify public key hashes to the address
    if generate_p2pkh_address(public_key) != address_from_lock:
        return False

    # Verify the signature
    signature_bytes = base64.b64decode(sig_b64)
    return verify_signature(public_key, signature_bytes, transaction_hash.encode('utf-8'))
