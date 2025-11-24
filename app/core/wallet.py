from typing import List, Dict, Optional
import base64

from . import crypto
from .models import Transaction, TransactionInput, TransactionOutput
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def create_signed_transaction(
    sender_private_key: str,
    recipient_address: str,
    amount: float,
    fee: float,
    lock_height: Optional[int],
    sender_address: str,
    sender_utxos: Dict
) -> Transaction:

    amount_to_send = amount + fee
    utxos_to_spend = {}
    total_input = 0
    for key, utxo in sender_utxos.items():
        utxos_to_spend[key] = utxo
        total_input += utxo['value']
        if total_input >= amount_to_send:
            break

    if total_input < amount_to_send:
        raise ValueError("Insufficient funds.")

    outputs = [TransactionOutput(value=amount, script_pub_key=crypto.create_p2pkh_locking_script(recipient_address), lock_height=lock_height)]
    change = total_input - amount_to_send
    if change > 0:
        outputs.append(TransactionOutput(value=change, script_pub_key=crypto.create_p2pkh_locking_script(sender_address)))

    inputs = [TransactionInput(transaction_id=k.split(':')[0], output_index=int(k.split(':')[1]), script_sig="") for k in utxos_to_spend.keys()]

    temp_tx = Transaction(id="temp", inputs=inputs, outputs=outputs)
    tx_hash = crypto.sha256_hash(temp_tx.json(exclude={'id'}).encode())

    private_key = load_pem_private_key(base64.b64decode(sender_private_key), password=None)
    public_key = private_key.public_key()

    signature = crypto.sign_message(private_key, tx_hash.encode())
    sig_b64 = base64.b64encode(signature).decode('utf-8')
    pub_key_b64 = crypto.serialize_public_key(public_key)

    # This is missing! Let's add create_p2pkh_unlocking_script to crypto.py
    # For now, let's just create the string manually
    unlocking_script = f"{sig_b64} {pub_key_b64}"

    for i in inputs:
        i.script_sig = unlocking_script

    return Transaction(id=tx_hash, inputs=inputs, outputs=outputs)
