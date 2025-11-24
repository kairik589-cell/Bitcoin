from typing import List, Dict
from copy import deepcopy
import time

from .models import Block, BlockHeader, Transaction, TransactionOutput
from . import crypto
from .blockchain import calculate_mining_reward

def calculate_merkle_root(transactions: List[Transaction]) -> str:
    if not transactions: return "0" * 64
    tx_ids = [tx.id for tx in transactions]
    while len(tx_ids) > 1:
        if len(tx_ids) % 2 != 0: tx_ids.append(tx_ids[-1])
        new_level = [crypto.sha256_hash((tx_ids[i] + tx_ids[i+1]).encode()) for i in range(0, len(tx_ids), 2)]
        tx_ids = new_level
    return tx_ids[0]

def find_nonce(header: BlockHeader) -> int:
    header_copy = deepcopy(header)
    prefix = '0' * header_copy.difficulty_target
    nonce = 0
    while True:
        header_copy.nonce = nonce
        header_string = f"{header_copy.version}{header_copy.previous_block_hash}{header_copy.merkle_root}{header_copy.timestamp}{header_copy.difficulty_target}{header_copy.nonce}".encode()
        hash_result = crypto.sha256_hash(header_string)
        if hash_result.startswith(prefix):
            return nonce
        nonce += 1

from typing import Tuple
from .blockchain import blockchain_instance
from .config import settings
from .database import get_utxos_collection, get_mempool_collection

async def calculate_transaction_fee(transaction: Transaction) -> float:
    """Calculates the fee for a single transaction by fetching its input UTXOs."""
    if not transaction.inputs:
        return 0.0

    utxos_collection = get_utxos_collection()
    input_utxo_ids = [f"{tin.transaction_id}:{tin.output_index}" for tin in transaction.inputs]

    utxos_cursor = utxos_collection.find({"_id": {"$in": input_utxo_ids}})
    input_utxos = await utxos_cursor.to_list(length=None)

    if len(input_utxos) != len(input_utxo_ids):
        return -1.0

    total_input_value = sum(utxo['value'] for utxo in input_utxos)
    total_output_value = sum(tout.value for tout in transaction.outputs)

    fee = total_input_value - total_output_value
    return fee

async def adjust_difficulty(previous_block: Dict) -> int:
    """
    Adjusts the mining difficulty every DIFFICULTY_ADJUSTMENT_INTERVAL blocks.
    """
    height = previous_block['header']['height']

    if (height + 1) % settings.DIFFICULTY_ADJUSTMENT_INTERVAL != 0:
        return previous_block['header']['difficulty_target']

    interval_start_height = height - (settings.DIFFICULTY_ADJUSTMENT_INTERVAL - 1)

    start_block = await blockchain_instance.get_block_by_height(interval_start_height)
    if not start_block:
        return settings.MINING_DIFFICULTY

    start_time = start_block['header']['timestamp']
    end_time = previous_block['header']['timestamp']

    actual_time = end_time - start_time
    expected_time = settings.DIFFICULTY_ADJUSTMENT_INTERVAL * settings.TARGET_BLOCK_TIME

    ratio = actual_time / expected_time

    # Clamp the adjustment factor to avoid drastic changes
    ratio = max(0.25, min(4.0, ratio))

    new_difficulty_float = previous_block['header']['difficulty_target'] / ratio

    # For simplicity, we'll use integer difficulty. A real system uses a target hash.
    new_difficulty = int(round(new_difficulty_float))

    # Ensure difficulty does not fall below a minimum value
    return max(1, new_difficulty)

async def mine_new_block(miner_address: str) -> Tuple[Block, List[str]]:
    """
    Mines a new block by fetching transactions from the centralized mempool.
    Returns the new block and a list of the mined transaction IDs.
    """
    mempool_collection = get_mempool_collection()
    mempool_docs = await mempool_collection.find().to_list(length=1000) # Limit block size
    mempool_txs = [Transaction(**doc['transaction']) for doc in mempool_docs]

    last_block = await blockchain_instance.get_last_block()
    height = last_block['header']['height'] + 1 if last_block else 0
    previous_block_hash = last_block['hash'] if last_block else "0" * 64

    tx_with_fees = []
    for tx in mempool_txs:
        fee = await calculate_transaction_fee(tx)
        if fee >= 0:
            tx_with_fees.append({"tx": tx, "fee": fee})

    tx_with_fees.sort(key=lambda x: x['fee'], reverse=True)

    transactions_for_block_without_coinbase = [item['tx'] for item in tx_with_fees]
    mined_tx_ids = [tx.id for tx in transactions_for_block_without_coinbase]
    total_fees = sum(item['fee'] for item in tx_with_fees)

    reward = calculate_mining_reward(height)
    coinbase_tx = Transaction(
        id=f"coinbase_{height}",
        inputs=[],
        outputs=[TransactionOutput(value=reward + total_fees, script_pub_key=crypto.create_p2pkh_locking_script(miner_address))]
    )

    transactions_for_block = [coinbase_tx] + transactions_for_block_without_coinbase
    merkle_root = calculate_merkle_root(transactions_for_block)

    difficulty = await adjust_difficulty(last_block) if last_block else settings.MINING_DIFFICULTY

    header = BlockHeader(
        previous_block_hash=previous_block_hash,
        merkle_root=merkle_root,
        timestamp=time.time(),
        difficulty_target=difficulty,
        nonce=0,
        height=height
    )

    nonce = find_nonce(header)
    header.nonce = nonce

    hash_string = f"{header.version}{header.previous_block_hash}{header.merkle_root}{header.timestamp}{header.difficulty_target}{header.nonce}".encode()
    block_hash = crypto.sha256_hash(hash_string)

    new_block = Block(hash=block_hash, header=header, transactions=transactions_for_block)

    return new_block, mined_tx_ids
