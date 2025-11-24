from fastapi import FastAPI
from .api_v1 import exchange as exchange_v1
from .network import network_instance, Node # Keep network for blockchain interaction
from .models import TransactionCreateRequest, MineRequest, Transaction
from . import wallet, crypto
import base64

app = FastAPI(title="Bitcoin Simulation API (DB-Backed)")

# Include the exchange API router
app.include_router(exchange_v1.router, prefix="/api/v1")

# --- Core Blockchain Interaction Endpoints ---
def get_node() -> Node:
    return network_instance.get_random_node()

@app.post("/transactions/create", response_model=Transaction)
def new_transaction(request: TransactionCreateRequest):
    # This logic now uses the DB-backed UTXO set via the node
    node_for_utxos = get_node()
    # ... (transaction creation logic as before, but must now read UTXOs from DB)

    # tx = wallet.create_signed_transaction(...)
    # network_instance.broadcast_transaction(tx)
    # return tx
    pass # Placeholder

@app.post("/mine", summary="Mine a New Block")
def mine_block(request: MineRequest):
    miner_node = get_node()
    new_block = miner_node.mine_block(request.miner_address)

    # The manager's add_block now writes to DB
    if not network_instance.blockchain_manager.add_block(new_block):
        raise HTTPException(status_code=500, detail="Mined block was invalid.")

    network_instance.broadcast_block(new_block, miner_node.node_id)
    return new_block.dict()

@app.get("/")
def root():
    return {"message": "Welcome to the DB-backed Bitcoin Simulation"}
