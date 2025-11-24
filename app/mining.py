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

def adjust_difficulty(chain: List[Dict]) -> int:
    # Simplified difficulty adjustment
    return 4

def mine_new_block(mempool: List[Transaction], utxo_set: dict, chain: List[Dict], miner_address: str) -> Block:
    last_block = chain[-1] if chain else None
    height = last_block['header']['height'] + 1 if last_block else 0

    total_fees = 0 # Simplified fee calculation for now

    reward = calculate_mining_reward(height)
    coinbase_tx = Transaction(id=f"coinbase_{height}", inputs=[], outputs=[TransactionOutput(value=reward + total_fees, script_pub_key=crypto.create_p2pkh_locking_script(miner_address))])

    transactions_for_block = [coinbase_tx] + mempool
    merkle_root = calculate_merkle_root(transactions_for_block)
    difficulty = adjust_difficulty(chain)

    header = BlockHeader(
        previous_block_hash=last_block['hash'] if last_block else "0",
        merkle_root=merkle_root,
        timestamp=time.time(),
        difficulty_target=difficulty,
        nonce=0, height=height
    )

    nonce = find_nonce(header)
    header.nonce = nonce

    hash_string = f"{header.version}{header.previous_block_hash}{header.merkle_root}{header.timestamp}{header.difficulty_target}{header.nonce}".encode()
    block_hash = crypto.sha256_hash(hash_string)

    return Block(hash=block_hash, header=header, transactions=transactions_for_block)
