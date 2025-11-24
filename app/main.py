from fastapi import FastAPI, HTTPException
from app.api_v1 import exchange as exchange_v1, wallet as wallet_v1, explorer as explorer_v1
from app.core.models import TransactionCreateRequest, MineRequest, Transaction
from app.core import wallet, crypto, mining
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.blockchain import blockchain_instance
import base64

app = FastAPI(title="Bitcoin Simulation API (DB-Backed)")

from app.core.database import get_exchange_order_books_collection

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    await blockchain_instance.initialize()

    # Initialize default exchange market if it doesn't exist
    order_books = get_exchange_order_books_collection()
    if await order_books.count_documents({"_id": "SIM_COIN/USD"}) == 0:
        await order_books.insert_one({"_id": "SIM_COIN/USD", "bids": [], "asks": []})
        print("Initialized default SIM_COIN/USD market.")

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Include API routers
app.include_router(exchange_v1.router, prefix="/api/v1")
app.include_router(wallet_v1.router, prefix="/api/v1")
app.include_router(explorer_v1.router, prefix="/api/v1")

# --- Core Blockchain Interaction Endpoints ---
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from app.core.database import get_utxos_collection, get_mempool_collection
from pymongo.errors import DuplicateKeyError

@app.post("/transactions/create", response_model=Transaction, summary="Create a New Transaction")
async def new_transaction(request: TransactionCreateRequest):
    """
    Creates a new transaction, signs it, and adds it to the mempool.
    """
    try:
        private_key_bytes = base64.b64decode(request.sender_private_key)
        private_key = load_pem_private_key(private_key_bytes, password=None)
        public_key = private_key.public_key()
        sender_address = crypto.generate_p2pkh_address(public_key)

        utxos_collection = get_utxos_collection()
        sender_locking_script = crypto.create_p2pkh_locking_script(sender_address)

        utxos_cursor = utxos_collection.find({"script_pub_key": sender_locking_script})
        sender_utxos_list = await utxos_cursor.to_list(length=None)

        if not sender_utxos_list:
            raise HTTPException(status_code=400, detail="No spendable outputs (UTXOs) found.")

        sender_utxos_dict = {utxo["_id"]: utxo for utxo in sender_utxos_list}

        tx = wallet.create_signed_transaction(
            sender_private_key=request.sender_private_key,
            recipient_address=request.recipient_address,
            amount=request.amount,
            fee=request.fee,
            lock_height=request.lock_height,
            sender_address=sender_address,
            sender_utxos=sender_utxos_dict
        )

        # 4. Add the transaction to the centralized mempool
        mempool = get_mempool_collection()
        try:
            # We use the transaction ID as the document ID to prevent duplicates
            await mempool.insert_one({"_id": tx.id, "transaction": tx.dict()})
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail=f"Transaction {tx.id} already in mempool.")

        return tx

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.post("/mine", summary="Mine a New Block")
async def mine_block(request: MineRequest):
    """
    Mines a new block, adds it to the chain, and clears the mined
    transactions from the mempool.
    """
    # 1. Mine the block. This fetches transactions from the DB mempool.
    new_block, mined_tx_ids = await mining.mine_new_block(request.miner_address)

    # 2. Add the new block to the blockchain.
    if not await blockchain_instance.add_block(new_block):
        raise HTTPException(status_code=400, detail="Mined block was rejected by the blockchain.")

    # 3. Clear the mined transactions from the mempool.
    if mined_tx_ids:
        mempool = get_mempool_collection()
        await mempool.delete_many({"_id": {"$in": mined_tx_ids}})

    return new_block.dict()

@app.get("/")
def root():
    return {"message": "Welcome to the DB-backed Bitcoin Simulation"}
