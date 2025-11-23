from fastapi import FastAPI, HTTPException, Body
from typing import List, Dict

from .blockchain import blockchain_instance
from .models import (
    Block, Transaction, TransactionOutput, WalletCreateResponse,
    TransactionCreateRequest, MineRequest
)
from . import crypto
from . import mining
from . import wallet
from .api_v1 import wallet as wallet_v1, exchange as exchange_v1
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64

app = FastAPI(
    title="Bitcoin Simulation API",
    description="A comprehensive API simulating the core features of a Bitcoin-like blockchain.",
    version="0.1.0",
)

# --- API Explorer (Read-Only) Endpoints ---

@app.get("/stats", summary="Get Blockchain Statistics")
def get_stats():
    last_block = blockchain_instance.get_last_block()
    return {
        "block_height": len(blockchain_instance.chain),
        "last_block_hash": last_block.hash if last_block else None,
        "utxo_set_size": len(blockchain_instance.utxo_set),
        "mempool_size": len(blockchain_instance.mempool),
        "difficulty": last_block.header.difficulty_target if last_block else 1
    }

@app.get("/block/{block_hash}", response_model=Block, summary="Get Block by Hash")
def get_block(block_hash: str):
    for block in blockchain_instance.chain:
        if block.hash == block_hash:
            return block
    raise HTTPException(status_code=404, detail="Block not found")

@app.get("/transaction/{tx_id}", response_model=Transaction, summary="Get Transaction by ID")
def get_transaction(tx_id: str):
    for block in blockchain_instance.chain:
        for tx in block.transactions:
            if tx.id == tx_id:
                return tx
    for tx in blockchain_instance.mempool:
        if tx.id == tx_id:
            return tx
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.get("/mempool", response_model=List[Transaction], summary="View the Mempool")
def get_mempool():
    return blockchain_instance.mempool

@app.get("/address/{address}/utxos", response_model=Dict[str, TransactionOutput], summary="Get UTXOs for an Address")
def get_utxos_for_address(address: str):
    utxos = {}
    for key, utxo in blockchain_instance.utxo_set.items():
        if utxo.script_pub_key.split(' ')[2] == address:
            utxos[key] = utxo
    return utxos

# --- API Interaktif (Write) Endpoints ---

@app.post("/wallet/create", response_model=WalletCreateResponse, summary="Create a New Wallet")
def create_wallet():
    """
    Generates a new private key, public key, and a P2PKH address.
    """
    private_key = crypto.generate_private_key()
    public_key = crypto.get_public_key(private_key)
    address = crypto.generate_address(public_key)

    return WalletCreateResponse(
        private_key=crypto.serialize_private_key(private_key),
        public_key=crypto.serialize_public_key(public_key),
        address=address
    )

@app.post("/transactions/create", response_model=Transaction, summary="Create and Broadcast a New Transaction")
def new_transaction(request: TransactionCreateRequest = Body(...)):
    """
    Creates, signs, and broadcasts a new transaction to the mempool.
    """
    # 1. Derive sender's address from the private key
    try:
        private_key_bytes = base64.b64decode(request.sender_private_key)
        private_key = load_pem_private_key(private_key_bytes, password=None)
        public_key = crypto.get_public_key(private_key)
        sender_address = crypto.generate_address(public_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid private key.")

    # 2. Get UTXOs for the sender
    sender_utxos = get_utxos_for_address(sender_address)
    if not sender_utxos:
        raise HTTPException(status_code=400, detail="Address has no UTXOs to spend.")

    # 3. Create the signed transaction
    try:
        tx = wallet.create_signed_transaction(request, sender_address, sender_utxos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 4. Validate and add to mempool
    if blockchain_instance.add_transaction_to_mempool(tx):
        return tx
    else:
        raise HTTPException(status_code=500, detail="Transaction validation failed on the server.")

@app.post("/mine", response_model=Block, summary="Mine a New Block")
def mine_block(request: MineRequest = Body(...)):
    """
    Mines a new block, including all transactions from the mempool.
    """
    last_block = blockchain_instance.get_last_block()
    if not last_block:
        raise HTTPException(status_code=500, detail="Blockchain not initialized.")

    mempool_to_mine = list(blockchain_instance.mempool)

    new_block = mining.mine_new_block(
        mempool=mempool_to_mine,
        utxo_set=blockchain_instance.utxo_set,
        chain=blockchain_instance.chain,
        miner_address=request.miner_address
    )

    if blockchain_instance.add_block(new_block):
        # Clear the mempool of the mined transactions
        blockchain_instance.mempool = [tx for tx in blockchain_instance.mempool if tx not in mempool_to_mine]
        return new_block
    else:
        raise HTTPException(status_code=500, detail="Failed to add mined block to the chain.")

# --- API Validasi ---
@app.get("/chain/is-valid", summary="Validate the Blockchain's Integrity")
def is_chain_valid():
    """
    Runs a full validation on the blockchain to ensure its integrity.
    """
    is_valid = blockchain_instance.validate_chain()
    if is_valid:
        return {"message": "The blockchain is valid."}
    else:
        raise HTTPException(status_code=500, detail="The blockchain is invalid!")


# --- Root Endpoint ---
# --- API v1 Routers ---
app.include_router(wallet_v1.router, prefix="/api/v1")
app.include_router(exchange_v1.router, prefix="/api/v1")

# --- Root Endpoint ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Bitcoin Simulation API. Check out the /docs for interactive API documentation."}
