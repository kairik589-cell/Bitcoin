from typing import List, Dict
import time

from . import crypto
from .models import Transaction, TransactionInput, TransactionOutput, TransactionCreateRequest
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64

def create_signed_transaction(
    sender_private_key, # Can be b64 string or private_key object
    recipient_address: str,
    amount: float,
    fee: float,
    sender_address: str,
    sender_utxos: Dict[str, TransactionOutput]
) -> Transaction:
    """
    Creates a new, signed transaction based on a request.
    This is a core function for the wallet.
    """

    # 1. Select UTXOs to cover the amount + fee
    utxos_to_spend: Dict[str, TransactionOutput] = {}
    total_input_value = 0
    amount_to_send = amount + fee

    for key, utxo in sender_utxos.items():
        utxos_to_spend[key] = utxo
        total_input_value += utxo.value
        if total_input_value >= amount_to_send:
            break

    if total_input_value < amount_to_send:
        raise ValueError("Insufficient funds to create the transaction.")

    # 2. Create the transaction outputs
    outputs = [
        TransactionOutput(
            value=amount,
            script_pub_key=crypto.create_p2pkh_locking_script(recipient_address)
        )
    ]

    # Add a "change" output if there's leftover value
    change = total_input_value - amount_to_send
    if change > 0:
        outputs.append(
            TransactionOutput(
                value=change,
                script_pub_key=crypto.create_p2pkh_locking_script(sender_address)
            )
        )

    # 3. Create the unsigned transaction inputs
    inputs_unsigned = []
    for key in utxos_to_spend.keys():
        tx_id, output_index = key.split(':')
        inputs_unsigned.append(
            TransactionInput(
                transaction_id=tx_id,
                output_index=int(output_index),
                script_sig="" # Placeholder for the signature
            )
        )

    # Create a temporary transaction to get its hash for signing
    temp_tx = Transaction(id="temp_id", inputs=inputs_unsigned, outputs=outputs)
    tx_hash = crypto.sha256_hash(temp_tx.json(exclude={'id'}).encode())

    # 4. Sign the inputs
    if isinstance(sender_private_key, str):
        private_key_bytes = base64.b64decode(sender_private_key)
        private_key = load_pem_private_key(private_key_bytes, password=None)
    else:
        private_key = sender_private_key # It's already a private_key object

    public_key = crypto.get_public_key(private_key)
    public_key_b64 = crypto.serialize_public_key(public_key)

    signature = crypto.sign_message(private_key, tx_hash.encode())
    signature_b64 = base64.b64encode(signature).decode('utf-8')

    script_sig = crypto.create_p2pkh_unlocking_script(signature_b64, public_key_b64)

    # 5. Create the final, signed inputs
    signed_inputs = []
    for key in utxos_to_spend.keys():
        tx_id, output_index = key.split(':')
        signed_inputs.append(
            TransactionInput(
                transaction_id=tx_id,
                output_index=int(output_index),
                script_sig=script_sig
            )
        )

    # 6. Create the final transaction with a real ID
    final_tx = Transaction(id=tx_hash, inputs=signed_inputs, outputs=outputs)

    return final_tx
