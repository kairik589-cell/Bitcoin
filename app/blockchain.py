import time
from typing import Dict, List, Optional

from .models import Block, BlockHeader, Transaction, TransactionOutput
from . import crypto
from .database import blocks_collection, utxos_collection

HALVING_INTERVAL = 10; INITIAL_MINING_REWARD = 50.0

def calculate_mining_reward(height: int) -> float:
    return INITIAL_MINING_REWARD / (2 ** (height // HALVING_INTERVAL))

class Blockchain:
    def __init__(self):
        if blocks_collection.count_documents({}) == 0:
            self._create_genesis_block()

    def _create_genesis_block(self):
        reward = calculate_mining_reward(0)
        genesis_tx = Transaction(id="genesis_tx_0", inputs=[], outputs=[TransactionOutput(value=reward, script_pub_key="genesis_lock")])
        header = BlockHeader(previous_block_hash="0", merkle_root=crypto.sha256_hash(genesis_tx.id.encode()), timestamp=time.time(), difficulty_target=1, nonce=0, height=0)
        block = Block(hash=self._hash_block_header(header), header=header, transactions=[genesis_tx])

        blocks_collection.insert_one(block.dict())
        utxo_data = genesis_tx.outputs[0].dict()
        utxo_data["_id"] = f"{genesis_tx.id}:0"
        utxos_collection.insert_one(utxo_data)

    def get_last_block(self) -> Optional[Dict]:
        try:
            return blocks_collection.find().sort("header.height", -1).limit(1)[0]
        except IndexError: return None

    def _hash_block_header(self, h: BlockHeader) -> str:
        data = f"{h.version}{h.previous_block_hash}{h.merkle_root}{h.timestamp}{h.difficulty_target}{h.nonce}".encode()
        return crypto.sha256_hash(data)

    def add_block(self, block: Block) -> bool:
        last_block = self.get_last_block()
        if not last_block or block.header.previous_block_hash != last_block['hash']: return False

        height = last_block['header']['height'] + 1
        utxo_snapshot = {u["_id"]: u for u in utxos_collection.find()}

        utxos_to_delete = []
        utxos_to_add = []

        for tx in block.transactions:
            if not tx.inputs: continue # Skip coinbase

            for tin in tx.inputs:
                utxo_key = f"{tin.transaction_id}:{tin.output_index}"
                utxo = utxo_snapshot.get(utxo_key)
                if not utxo: return False # Invalid input
                if utxo.get("lock_height") and height < utxo["lock_height"]: return False # CLTV fail
                utxos_to_delete.append(utxo_key)

            for i, tout in enumerate(tx.outputs):
                utxos_to_add.append({"_id": f"{tx.id}:{i}", **tout.dict()})

        # Handle coinbase UTXO separately
        coinbase_tx = block.transactions[0]
        for i, tout in enumerate(coinbase_tx.outputs):
            utxos_to_add.append({"_id": f"{coinbase_tx.id}:{i}", **tout.dict()})

        # DB operations
        if utxos_to_delete: utxos_collection.delete_many({"_id": {"$in": utxos_to_delete}})
        if utxos_to_add: utxos_collection.insert_many(utxos_to_add)
        blocks_collection.insert_one(block.dict())

        return True
