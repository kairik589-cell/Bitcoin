from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import base64

from app.core import crypto
from app.core.database import get_utxos_collection, get_blocks_collection
from app.core.models import Transaction

router = APIRouter(prefix="/wallet", tags=["Wallet"])

class WalletDetails(BaseModel):
    private_key_b64: str
    public_key_b64: str
    address: str

class BalanceDetails(BaseModel):
    address: str
    balance: float

@router.post("/create", response_model=WalletDetails, summary="Create a New Wallet")
def create_wallet():
    """
    Generates a new cryptographic key pair (private and public keys) and a
    corresponding P2PKH address.
    """
    private_key = crypto.generate_private_key()
    public_key = crypto.get_public_key(private_key)

    private_key_pem = private_key.private_bytes(
        encoding=crypto.Encoding.PEM,
        format=crypto.PrivateFormat.PKCS8,
        encryption_algorithm=crypto.NoEncryption()
    )
    private_key_b64 = base64.b64encode(private_key_pem).decode('utf-8')

    public_key_b64 = crypto.serialize_public_key(public_key)
    address = crypto.generate_p2pkh_address(public_key)

    return WalletDetails(
        private_key_b64=private_key_b64,
        public_key_b64=public_key_b64,
        address=address
    )

@router.get("/balance/{address}", response_model=BalanceDetails, summary="Get Wallet Balance")
async def get_balance(address: str):
    """
    Calculates and returns the balance for a given address by summing up its UTXOs.
    """
    utxos_collection = get_utxos_collection()
    locking_script = crypto.create_p2pkh_locking_script(address)

    pipeline = [
        {"$match": {"script_pub_key": locking_script}},
        {"$group": {"_id": None, "total_value": {"$sum": "$value"}}}
    ]

    result = await utxos_collection.aggregate(pipeline).to_list(length=1)

    balance = result[0]['total_value'] if result else 0.0

    return BalanceDetails(address=address, balance=balance)

@router.get("/transactions/{address}", response_model=List[Transaction], summary="Get Transaction History")
async def get_transaction_history(address: str):
    """
    Retrieves the transaction history for a given address.
    Note: This is a simplified and potentially slow implementation.
    A real-world application would use a more optimized indexing strategy.
    """
    blocks_collection = get_blocks_collection()
    locking_script = crypto.create_p2pkh_locking_script(address)

    # Find all transactions where the address is in the output
    pipeline = [
        {"$unwind": "$transactions"},
        {"$match": {"transactions.outputs.script_pub_key": locking_script}},
        {"$replaceRoot": {"newRoot": "$transactions"}}
    ]

    cursor = blocks_collection.aggregate(pipeline)
    transactions = await cursor.to_list(length=None)

    return transactions
