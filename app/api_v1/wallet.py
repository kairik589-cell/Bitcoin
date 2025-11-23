from fastapi import APIRouter, HTTPException
from typing import List

from app.blockchain import blockchain_instance
from app.models import Transaction

router = APIRouter(
    prefix="/wallet",
    tags=["Wallet v1"],
)

@router.get("/{address}/balance", summary="Get Address Balance")
def get_address_balance(address: str):
    """
    Calculates and returns the total balance for a given address
    by summing up the values of its UTXOs.
    """
    balance = 0
    utxos = {}
    for key, utxo in blockchain_instance.utxo_set.items():
        if utxo.script_pub_key.split(' ')[2] == address:
            balance += utxo.value
            utxos[key] = utxo

    return {"address": address, "balance": balance, "utxo_count": len(utxos)}

@router.get("/{address}/history", summary="Get Simplified Transaction History")
def get_transaction_history(address: str) -> List[dict]:
    """
    Provides a simplified transaction history for a given address.
    """
    history = []
    for block in blockchain_instance.chain:
        for tx in block.transactions:
            is_sender = False
            is_recipient = False

            # Check if address is a recipient
            for output in tx.outputs:
                if output.script_pub_key.split(' ')[2] == address:
                    is_recipient = True
                    history.append({
                        "type": "receive",
                        "amount": output.value,
                        "tx_id": tx.id,
                        "block_hash": block.hash
                    })

            # Check if address is a sender (by checking if it owned an input)
            for tx_input in tx.inputs:
                utxo_key = f"{tx_input.transaction_id}:{tx_input.output_index}"
                # This is a simplification; we can't look up past UTXOs easily.
                # A full implementation would need an indexed database.
                # For now, we just indicate an outgoing transaction without the amount.
                # A better approach would be to look up the input transaction.

                # Let's try to look it up
                input_tx_found = None
                for past_block in blockchain_instance.chain:
                    for past_tx in past_block.transactions:
                        if past_tx.id == tx_input.transaction_id:
                            input_tx_found = past_tx
                            break
                    if input_tx_found:
                        break

                if input_tx_found:
                    try:
                        spent_output = input_tx_found.outputs[tx_input.output_index]
                        if spent_output.script_pub_key.split(' ')[2] == address:
                            is_sender = True
                            # To avoid double counting, we add a single 'send' entry
                            break
                    except IndexError:
                        continue

            if is_sender:
                total_sent_from_address = 0
                for tx_input in tx.inputs:
                     # Re-fetch the transaction to find the value of the spent output
                    input_tx_found = None
                    for past_block in blockchain_instance.chain:
                        for past_tx in past_block.transactions:
                            if past_tx.id == tx_input.transaction_id:
                                input_tx_found = past_tx
                                break
                        if input_tx_found:
                            break
                    if input_tx_found:
                        try:
                            spent_output = input_tx_found.outputs[tx_input.output_index]
                            if spent_output.script_pub_key.split(' ')[2] == address:
                                total_sent_from_address += spent_output.value
                        except IndexError:
                            continue

                history.append({
                        "type": "send",
                        "amount": -total_sent_from_address,
                        "tx_id": tx.id,
                        "block_hash": block.hash
                    })

    return history
