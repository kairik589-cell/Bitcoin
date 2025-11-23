from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict

import uuid
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64

from app.network import network_instance
from app.models import Transaction
from app import wallet, crypto

router = APIRouter(prefix="/wallet", tags=["Wallet v1"])

loaded_wallets = {}

class LoadWalletRequest(BaseModel):
    private_key_b64: str

class SessionTransactionRequest(BaseModel):
    session_id: str; recipient_address: str; amount: float; fee: float = 0.0

def get_utxos_for_address_from_node(address: str) -> Dict:
    node = network_instance.get_random_node()
    utxos = {}
    for key, utxo in node.blockchain.utxo_set.items():
        try:
            if utxo.script_pub_key.split(' ')[-2] == address:
                utxos[key] = utxo
        except IndexError:
            continue
    return utxos

@router.post("/load", summary="Load a Wallet for a Session")
def load_wallet(request: LoadWalletRequest):
    try:
        private_key = load_pem_private_key(base64.b64decode(request.private_key_b64), password=None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid private key.")

    session_id = str(uuid.uuid4())
    loaded_wallets[session_id] = private_key
    address = crypto.generate_p2pkh_address(private_key.public_key())

    return {"message": "Wallet loaded", "session_id": session_id, "address": address}

@router.post("/unload/{session_id}", summary="Unload a Wallet from a Session")
def unload_wallet(session_id: str):
    if session_id in loaded_wallets:
        del loaded_wallets[session_id]
        return {"message": "Wallet unloaded."}
    raise HTTPException(status_code=404, detail="Session not found.")

@router.post("/transactions/create/session", response_model=Transaction, summary="Create Transaction using a Session")
def create_transaction_with_session(request: SessionTransactionRequest = Body(...)):
    if request.session_id not in loaded_wallets:
        raise HTTPException(status_code=404, detail="Session not found.")

    private_key = loaded_wallets[request.session_id]
    sender_address = crypto.generate_p2pkh_address(private_key.public_key())
    sender_utxos = get_utxos_for_address_from_node(sender_address)

    if not sender_utxos:
        raise HTTPException(status_code=400, detail="Address has no UTXOs to spend.")

    try:
        tx = wallet.create_signed_transaction(
            sender_private_key=private_key,
            recipient_address=request.recipient_address,
            amount=request.amount, fee=request.fee,
            sender_address=sender_address, sender_utxos=sender_utxos
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    network_instance.broadcast_transaction(tx)
    return tx

@router.get("/{address}/balance", summary="Get Address Balance")
def get_address_balance(address: str):
    balance = 0
    utxos = get_utxos_for_address_from_node(address)
    for utxo in utxos.values():
        balance += utxo.value
    return {"address": address, "balance": balance, "utxo_count": len(utxos)}

# History endpoint would also need refactoring to query a node, omitted for brevity.
