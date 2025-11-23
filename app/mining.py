import time
from typing import List
from copy import deepcopy

from .models import Block, BlockHeader, Transaction, TransactionInput, TransactionOutput
from . import crypto
from .blockchain import calculate_mining_reward

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


# --- Difficulty Adjustment ---

DIFFICULTY_ADJUSTMENT_INTERVAL: int = 5  # blocks
BLOCK_GENERATION_INTERVAL: int = 30     # seconds, target time per block
EXPECTED_TIME_PER_INTERVAL = DIFFICULTY_ADJUSTMENT_INTERVAL * BLOCK_GENERATION_INTERVAL

def adjust_difficulty(chain: List[Block]) -> int:
    """
    Adjusts the mining difficulty every `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
    If blocks are mined too fast, difficulty increases. If too slow, it decreases.
    """
    last_block = chain[-1]
    current_height = len(chain)

    # Return the last block's difficulty if it's not time for an adjustment
    if current_height % DIFFICULTY_ADJUSTMENT_INTERVAL != 0 or current_height == 0:
        return last_block.header.difficulty_target

    previous_adjustment_block = chain[current_height - DIFFICULTY_ADJUSTMENT_INTERVAL]
    time_taken = last_block.header.timestamp - previous_adjustment_block.header.timestamp

    # If mining was more than twice as fast as expected, increase difficulty
    if time_taken < EXPECTED_TIME_PER_INTERVAL / 2:
        return last_block.header.difficulty_target + 1
    # If mining was more than twice as slow, decrease difficulty
    elif time_taken > EXPECTED_TIME_PER_INTERVAL * 2:
        return max(1, last_block.header.difficulty_target - 1)

    return last_block.header.difficulty_target


# --- Block Mining Orchestrator ---

def mine_new_block(mempool: List[Transaction], utxo_set: dict, chain: List[Block], miner_address: str) -> Block:
    """
    Orchestrates the entire process of creating a new block.
    """
    last_block = chain[-1]
    # 1. Calculate transaction fees
    total_fees = 0
    for tx in mempool:
        # Calculate the total value of inputs by looking up the UTXOs
        total_input_value = sum(
            utxo_set[f"{tx_input.transaction_id}:{tx_input.output_index}"].value
            for tx_input in tx.inputs
        )
        # Calculate the total value of outputs
        total_output_value = sum(tx_output.value for tx_output in tx.outputs)

        # The fee is the difference
        total_fees += (total_input_value - total_output_value)

    # 2. Create the coinbase transaction
    block_height = len(chain)
    mining_reward = calculate_mining_reward(block_height)

    coinbase_output = TransactionOutput(
        value=mining_reward + total_fees,
        script_pub_key=crypto.create_p2pkh_locking_script(miner_address)
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
    difficulty = adjust_difficulty(chain)
    new_timestamp = time.time()

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
