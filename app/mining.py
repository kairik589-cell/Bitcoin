import time
from typing import List
from copy import deepcopy

from .models import Block, BlockHeader, Transaction, TransactionInput, TransactionOutput
from . import crypto
from .blockchain import MINING_REWARD

# --- Merkle Tree ---

def calculate_merkle_root(transactions: List[Transaction]) -> str:
    """
    Calculates the Merkle root from a list of transaction IDs.
    """
    if not transactions:
        return "0" * 64

    tx_ids = [tx.id for tx in transactions]

    # Recursively hash pairs of nodes
    while len(tx_ids) > 1:
        # Make sure we have an even number of nodes
        if len(tx_ids) % 2 != 0:
            tx_ids.append(tx_ids[-1])

        new_level = []
        for i in range(0, len(tx_ids), 2):
            combined_hash = crypto.sha256_hash((tx_ids[i] + tx_ids[i+1]).encode())
            new_level.append(combined_hash)
        tx_ids = new_level

    return tx_ids[0]

# --- Proof-of-Work ---

def find_nonce(header: BlockHeader) -> int:
    """
    Finds a nonce that satisfies the block's difficulty target (Proof-of-Work).
    The hash of the block header must start with `difficulty_target` number of zeros.
    """
    header_copy = deepcopy(header)
    nonce = 0
    prefix = '0' * header_copy.difficulty_target

    while True:
        header_copy.nonce = nonce

        # In a real implementation, we would hash the serialized header bytes
        header_string = (
            str(header_copy.version) +
            header_copy.previous_block_hash +
            header_copy.merkle_root +
            str(header_copy.timestamp) +
            str(header_copy.difficulty_target) +
            str(header_copy.nonce)
        ).encode()

        hash_result = crypto.sha256_hash(header_string)

        if hash_result.startswith(prefix):
            return nonce

        nonce += 1


# --- Difficulty Adjustment (Placeholder) ---

def adjust_difficulty(last_block: Block, new_block_timestamp: float) -> int:
    """
    Adjusts the mining difficulty.
    For this simulation, we'll keep it simple and fixed for now.
    A real implementation would adjust based on the time taken to mine previous blocks.
    """
    # Placeholder: Fixed difficulty
    return 4

# --- Block Mining Orchestrator ---

def mine_new_block(mempool: List[Transaction], last_block: Block, miner_address: str) -> Block:
    """
    Orchestrates the entire process of creating a new block.
    """
    # 1. Calculate transaction fees
    total_fees = 0
    # (A full implementation would require the Blockchain instance to calculate fees)
    # For now, we'll assume fees are zero for simplicity.

    # 2. Create the coinbase transaction
    coinbase_output = TransactionOutput(
        value=MINING_REWARD + total_fees,
        script_pub_key=crypto.create_script_pub_key(miner_address)
    )
    coinbase_tx = Transaction(
        id=crypto.sha256_hash(str(time.time()).encode()), # Simple unique ID for coinbase
        inputs=[],
        outputs=[coinbase_output]
    )

    # 3. Prepare list of transactions for the block
    transactions_for_block = [coinbase_tx] + mempool

    # 4. Calculate Merkle Root
    merkle_root = calculate_merkle_root(transactions_for_block)

    # 5. Determine new difficulty
    new_timestamp = time.time()
    difficulty = adjust_difficulty(last_block, new_timestamp)

    # 6. Create the block header
    new_header = BlockHeader(
        previous_block_hash=last_block.hash,
        merkle_root=merkle_root,
        timestamp=new_timestamp,
        difficulty_target=difficulty,
        nonce=0 # Placeholder, will be found by PoW
    )

    # 7. Find the nonce (Proof-of-Work)
    nonce = find_nonce(new_header)
    new_header.nonce = nonce

    # 8. Hash the final header to get the block hash
    block_hash = crypto.sha256_hash((
        str(new_header.version) + new_header.previous_block_hash +
        new_header.merkle_root + str(new_header.timestamp) +
        str(new_header.difficulty_target) + str(new_header.nonce)
    ).encode())

    # 9. Create the final block
    new_block = Block(
        hash=block_hash,
        header=new_header,
        transactions=transactions_for_block
    )

    return new_block
