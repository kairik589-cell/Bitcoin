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

def evaluate_p2pkh_script(script_sig: str, script_pub_key: str, transaction_hash: str) -> bool:
    """
    Evaluates a P2PKH script by verifying the signature against the public key
    and the public key against the address in the locking script.
    """
    try:
        # 1. Parse the scripts
        sig_b64, pub_key_b64 = script_sig.split()
        script_type, address = script_pub_key.split()

        if script_type != "P2PKH":
            return False

        # 2. Verify that the public key hashes to the address
        public_key_bytes = base64.b64decode(pub_key_b64)
        public_key = load_pem_public_key(public_key_bytes)

        derived_address = generate_p2pkh_address(public_key)
        if derived_address != address:
            return False

        # 3. Verify the signature
        signature = base64.b64decode(sig_b64)
        message = transaction_hash.encode('utf-8')

        return verify_signature(public_key, signature, message)

    except Exception:
        # If any parsing or cryptographic operation fails, the script is invalid
        return False
