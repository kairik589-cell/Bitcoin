from fastapi import FastAPI, HTTPException, Body
from typing import List, Dict

# Replace the single blockchain instance with the network instance
from .network import network_instance, Node
from .models import (
    Block, Transaction, TransactionOutput, WalletCreateResponse,
    TransactionCreateRequest, MineRequest, MultiSigWalletCreateRequest,
    TokenIssuanceRequest, TokenTransferRequest, TokenIssuanceTransaction,
    TokenTransferTransaction
)
from . import crypto
from . import wallet
from .api_v1 import wallet as wallet_v1, exchange as exchange_v1
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64

app = FastAPI(
    title="Bitcoin Simulation API (P2P Simulated)",
    description="An API simulating a Bitcoin-like blockchain with a simulated P2P network.",
    version="0.2.0",
)

# Helper to get a consistent node for a request if needed, or just a random one
def get_node() -> Node:
    return network_instance.get_random_node()

# --- API Explorer (Read-Only) Endpoints ---
# These now query a random node's version of the truth.

@app.get("/stats", summary="Get Blockchain Statistics from a Node")
def get_stats():
    node = get_node()
    last_block = node.blockchain.get_last_block()
    return {
        "node_id": node.node_id,
        "block_height": len(node.blockchain.chain),
        "last_block_hash": last_block.hash if last_block else None,
        "mempool_size": len(node.mempool),
    }

# ... (Other read-only endpoints like get_block, get_transaction, etc., would be similarly refactored) ...
# For brevity, we'll focus on the core write operations.

@app.get("/block/height/{height}", response_model=Block, summary="Get Block by Height from a Node")
def get_block_by_height(height: int):
    node = get_node()
    if height < 0 or height >= len(node.blockchain.chain):
        raise HTTPException(status_code=404, detail="Block height is out of range on queried node.")
    return node.blockchain.chain[height]

@app.get("/stats/rich-list", summary="Get Top Richest Addresses from a Node")
def get_rich_list(top_n: int = 10):
    node = get_node()
    balances = {}
    for utxo in node.blockchain.utxo_set.values():
        try:
            address = utxo.script_pub_key.split(' ')[-2]
            balances[address] = balances.get(address, 0) + utxo.value
        except (IndexError, AttributeError):
            continue

    sorted_balances = sorted(balances.items(), key=lambda item: item[1], reverse=True)
    return sorted_balances[:top_n]

@app.get("/address/{address}/utxos", response_model=Dict[str, TransactionOutput], summary="Get UTXOs for an Address from a Node")
def get_utxos_for_address(address: str):
    # This should be consistent across nodes unless there's a fork.
    node = get_node()
    utxos = {}
    for key, utxo in node.blockchain.utxo_set.items():
        if utxo.script_pub_key.split(' ')[-2] == address:
            utxos[key] = utxo
    return utxos

# --- API Interaktif (Write) Endpoints ---

@app.post("/transactions/create", response_model=Transaction, summary="Broadcast a New Transaction to the Network")
def new_transaction(request: TransactionCreateRequest = Body(...)):
    # Create the transaction once
    # This logic now needs a specific node's UTXO set to create the tx
    node_for_utxos = get_node()
    sender_utxos = {}
    # ... (Logic to get sender_address)
    try:
        private_key_bytes = base64.b64decode(request.sender_private_key)
        private_key = load_pem_private_key(private_key_bytes, password=None)
        public_key = crypto.get_public_key(private_key)
        sender_address = crypto.generate_p2pkh_address(public_key)
    except Exception: raise HTTPException(status_code=400, detail="Invalid private key.")

    for key, utxo in node_for_utxos.blockchain.utxo_set.items():
        if utxo.script_pub_key.split(' ')[-2] == sender_address:
            sender_utxos[key] = utxo
    if not sender_utxos: raise HTTPException(status_code=400, detail="No UTXOs to spend.")

    tx = wallet.create_signed_transaction(
        sender_private_key=request.sender_private_key,
        recipient_address=request.recipient_address,
        amount=request.amount, fee=request.fee,
        sender_address=sender_address, sender_utxos=sender_utxos
    )

    # Broadcast to all nodes
    network_instance.broadcast_transaction(tx)

    return tx

@app.post("/mine", response_model=Block, summary="Mine a New Block on a Random Node")
def mine_block(request: MineRequest = Body(...)):
    # 1. Select a random node to be the "lucky" miner
    miner_node = get_node()

    # 2. The node mines a new block
    new_block = miner_node.mine_block(request.miner_address)

    # 3. The node's blockchain is updated locally
    if not miner_node.blockchain.add_block(new_block):
        raise HTTPException(status_code=500, detail="Mined block was invalid to its own creator.")

    # 4. The successful miner broadcasts the new block to the network
    network_instance.broadcast_block(new_block, miner_node.node_id)

    return new_block

# --- Other Endpoints (Wallet, Tokens, etc.) ---
# For this phase, we will simplify and assume they interact with a random node.
# A full implementation would require more sophisticated routing or state management.

# --- API v1 Routers ---
app.include_router(wallet_v1.router, prefix="/api/v1")
app.include_router(exchange_v1.router, prefix="/api/v1")

# --- Root Endpoint ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Bitcoin Simulation API (P2P)."}

# --- Wallet Creation ---
@app.post("/wallet/create", response_model=WalletCreateResponse, summary="Create a New Single-Signature Wallet")
def create_wallet():
    private_key = crypto.generate_private_key()
    public_key = crypto.get_public_key(private_key)
    address = crypto.generate_p2pkh_address(public_key)
    return WalletCreateResponse(
        private_key=crypto.serialize_private_key(private_key),
        public_key=crypto.serialize_public_key(public_key),
        address=address
    )

# @app.post("/wallet/multisig/create", summary="Create a New Multi-Signature Wallet [DISABLED]")
# def create_multisig_wallet(request: MultiSigWalletCreateRequest = Body(...)):
#     """
#     NOTE: This endpoint is disabled because the logic for SPENDING from a multi-sig
#     address is not yet implemented. This serves as a placeholder for future development.
#     """
#     if request.required_signatures > len(request.public_keys_b64):
#         raise HTTPException(status_code=400, detail="Required signatures cannot exceed the number of public keys.")

#     address = crypto.generate_multisig_address(request.public_keys_b64, request.required_signatures)
#     redeem_script = f"{request.required_signatures} {' '.join(request.public_keys_b64)}"
#     return {"multisig_address": address, "redeem_script": redeem_script}

# --- Token API Endpoints ---
# (Simplified helper for fee payments, adapted for P2P)
def _create_fee_tx_components_p2p(private_key_b64: str, fee: float):
    node = get_node()
    # ... (rest of the logic is the same as the old helper)
    private_key = load_pem_private_key(base64.b64decode(private_key_b64), password=None)
    public_key = crypto.get_public_key(private_key)
    sender_address = crypto.generate_p2pkh_address(public_key)

    sender_utxos = {k: v for k, v in node.blockchain.utxo_set.items() if v.script_pub_key.split(' ')[-2] == sender_address}
    if not sender_utxos: raise HTTPException(status_code=400, detail="Address has no UTXOs for fee.")

    utxos_to_spend, total_input = {}, 0
    for key, utxo in sender_utxos.items():
        utxos_to_spend[key], total_input = utxo, total_input + utxo.value
        if total_input >= fee: break
    if total_input < fee: raise HTTPException(status_code=400, detail="Insufficient funds for fee.")

    change = total_input - fee
    fee_outputs = [TransactionOutput(value=change, script_pub_key=crypto.create_p2pkh_locking_script(sender_address))] if change > 0 else []
    fee_inputs = [TransactionInput(transaction_id=k.split(':')[0], output_index=int(k.split(':')[1]), script_sig="") for k in utxos_to_spend.keys()]

    return fee_inputs, fee_outputs, private_key

@app.post("/tokens/issue", summary="Broadcast a Token Issuance Transaction")
def issue_token(request: TokenIssuanceRequest = Body(...)):
    fee_inputs, fee_outputs, private_key = _create_fee_tx_components_p2p(request.issuer_private_key, request.fee)
    issuer_address = crypto.generate_p2pkh_address(private_key.public_key())
    tx_id = crypto.sha256_hash(f"{request.token_id}{request.token_name}".encode())

    # Simplified signing for broadcast
    for i in fee_inputs:
        sig = crypto.sign_message(private_key, tx_id.encode())
        pub_key_b64 = crypto.serialize_public_key(private_key.public_key())
        i.script_sig = crypto.create_p2pkh_unlocking_script(base64.b64encode(sig).decode(), pub_key_b64)

    tx = TokenIssuanceTransaction(id=tx_id, fee_inputs=fee_inputs, fee_outputs=fee_outputs, token_id=request.token_id, token_name=request.token_name, total_supply=request.total_supply, issuer=issuer_address)

    # Broadcast to all nodes' token mempools
    for node in network_instance.nodes.values():
        if node.blockchain.validate_token_issuance(tx):
            node.token_mempool.append(tx)
    return tx

@app.post("/tokens/transfer", summary="Broadcast a Token Transfer Transaction")
def transfer_token(request: TokenTransferRequest = Body(...)):
    fee_inputs, fee_outputs, private_key = _create_fee_tx_components_p2p(request.sender_private_key, request.fee)
    sender_address = crypto.generate_p2pkh_address(private_key.public_key())
    tx_id = crypto.sha256_hash(f"{request.token_id}{sender_address}{request.recipient_address}{request.amount}".encode())

    for i in fee_inputs:
        sig = crypto.sign_message(private_key, tx_id.encode())
        pub_key_b64 = crypto.serialize_public_key(private_key.public_key())
        i.script_sig = crypto.create_p2pkh_unlocking_script(base64.b64encode(sig).decode(), pub_key_b64)

    tx = TokenTransferTransaction(id=tx_id, fee_inputs=fee_inputs, fee_outputs=fee_outputs, token_id=request.token_id, sender=sender_address, recipient=request.recipient_address, amount=request.amount)

    for node in network_instance.nodes.values():
        if node.blockchain.validate_token_transfer(tx):
            node.token_mempool.append(tx)
    return tx

@app.get("/tokens/{token_id}", summary="Get Token Information from a Node")
def get_token_info(token_id: str):
    node = get_node()
    if token_id not in node.blockchain.token_definitions:
        raise HTTPException(status_code=404, detail="Token not found on queried node.")
    return node.blockchain.token_definitions[token_id]

@app.get("/address/{address}/tokens", summary="Get Token Balances for an Address from a Node")
def get_token_balances_for_address(address: str):
    node = get_node()
    return node.blockchain.token_balances.get(address, {})
