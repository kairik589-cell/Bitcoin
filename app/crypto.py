import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption, load_pem_public_key
)

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

def serialize_public_key(public_key) -> str:
    pem = public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(pem).decode('utf-8')

def generate_p2pkh_address(public_key) -> str:
    serialized_key = serialize_public_key(public_key).encode('utf-8')
    return f"addr_{sha256_hash(serialized_key)[:30]}"

def create_p2pkh_locking_script(address: str) -> str:
    return f"P2PKH {address}"

def create_p2pkh_unlocking_script(signature_b64: str, public_key_b64: str) -> str:
    return f"{signature_b64} {public_key_b64}"
