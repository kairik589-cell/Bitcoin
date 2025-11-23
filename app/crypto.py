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

def generate_multisig_address(public_keys_b64: List[str], required_sigs: int) -> str:
    """Generates a multi-sig style address (hash of the redeem script)."""
    script_content = f"{required_sigs}_{'_'.join(sorted(public_keys_b64))}"
    return f"msig_{sha256_hash(script_content.encode())[:30]}"

# --- Scripting System ---

def create_p2pkh_locking_script(address: str) -> str:
    """Format: P2PKH <address>"""
    return f"P2PKH {address}"

def create_multisig_locking_script(address: str) -> str:
    """Format: P2SH <address> (Pay-to-Script-Hash)"""
    return f"P2SH {address}"

def create_p2pkh_unlocking_script(signature_b64: str, public_key_b64: str) -> str:
    """Format: <signature_b64> <public_key_b64>"""
    return f"{signature_b64} {public_key_b64}"

def create_multisig_unlocking_script(signatures_b64: List[str], public_keys_b64: List[str], required_sigs: int) -> str:
    """Format: <sig1_b64> <sig2_b64>... <required_sigs> <pubkey1_b64> <pubkey2_b64>..."""
    redeem_script = f"{required_sigs} {' '.join(public_keys_b64)}"
    return f"{' '.join(signatures_b64)} {redeem_script}"


def execute_script(unlocking_script: str, locking_script: str, transaction_hash: str) -> bool:
    """
    Simulates the execution of the Bitcoin scripting system.
    It now supports both P2PKH and P2SH (for Multi-sig).
    """
    script_type, script_param = locking_script.split(' ', 1)

    if script_type == "P2PKH":
        return _execute_p2pkh(unlocking_script, script_param, transaction_hash)
    elif script_type == "P2SH":
        return _execute_p2sh_multisig(unlocking_script, script_param, transaction_hash)

    return False

def _execute_p2pkh(unlocking_script: str, address_from_lock: str, tx_hash: str) -> bool:
    try:
        sig_b64, pub_key_b64 = unlocking_script.split(' ')
    except ValueError: return False

    public_key_bytes = base64.b64decode(pub_key_b64)
    public_key = load_pem_public_key(public_key_bytes)

    # Verify public key hashes to the address
    if generate_p2pkh_address(public_key) != address_from_lock:
        return False

    # Verify the signature
    signature_bytes = base64.b64decode(sig_b64)
    return verify_signature(public_key, signature_bytes, tx_hash.encode('utf-8'))

def _execute_p2sh_multisig(unlocking_script: str, address_from_lock: str, tx_hash: str) -> bool:
    try:
        # 1. Reconstruct the redeem script from the unlocking script
        parts = unlocking_script.split(' ')
        num_sigs = parts.count('') + 1 # A bit of a hack

        # Find where the public keys start
        pub_key_start_index = -1
        for i, part in enumerate(parts):
            if part.isdigit():
                pub_key_start_index = i
                break

        if pub_key_start_index == -1: return False

        signatures_b64 = parts[:pub_key_start_index]
        required_sigs = int(parts[pub_key_start_index])
        public_keys_b64 = parts[pub_key_start_index+1:]

        # 2. Verify that the redeem script hashes to the address in the locking script
        derived_address = generate_multisig_address(public_keys_b64, required_sigs)
        if derived_address != address_from_lock:
            return False

        # 3. Verify the signatures
        message_bytes = tx_hash.encode('utf-8')
        verified_sigs = 0
        sig_idx = 0
        for pub_key_b64 in public_keys_b64:
            if sig_idx >= len(signatures_b64): break

            public_key = load_pem_public_key(base64.b64decode(pub_key_b64))
            signature_bytes = base64.b64decode(signatures_b64[sig_idx])

            if verify_signature(public_key, signature_bytes, message_bytes):
                verified_sigs += 1
            sig_idx += 1

        return verified_sigs >= required_sigs
    except Exception:
        return False
