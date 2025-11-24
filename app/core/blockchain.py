import time
from typing import Dict, List, Optional

from .models import Block, BlockHeader, Transaction, TransactionOutput
from . import crypto
from .database import get_blocks_collection, get_utxos_collection
from .config import settings

# Use constants from config.py
HALVING_INTERVAL = settings.HALVING_INTERVAL
INITIAL_MINING_REWARD = settings.BLOCK_REWARD

def calculate_mining_reward(height: int) -> float:
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_MINING_REWARD / (2 ** halvings)

class Blockchain:
    def __init__(self):
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return
        blocks = get_blocks_collection()
        if await blocks.count_documents({}) == 0:
            await self._create_genesis_block()
        self.initialized = True

    async def _create_genesis_block(self):
        blocks = get_blocks_collection()
        utxos = get_utxos_collection()

        reward = calculate_mining_reward(0)
        genesis_tx = Transaction(
            id="genesis_tx_0",
            inputs=[],
            outputs=[TransactionOutput(value=reward, script_pub_key="genesis_lock")]
        )
        header = BlockHeader(
            previous_block_hash="0",
            merkle_root=crypto.sha256_hash(genesis_tx.id.encode()),
            timestamp=time.time(),
            difficulty_target=settings.MINING_DIFFICULTY,
            nonce=0,
            height=0
        )

        block_hash = self._hash_block_header(header)
        block = Block(hash=block_hash, header=header, transactions=[genesis_tx])

        await blocks.insert_one(block.dict())
        utxo_data = genesis_tx.outputs[0].dict()
        utxo_data["_id"] = f"{genesis_tx.id}:0"
        await utxos.insert_one(utxo_data)
        print("Genesis block created.")

    async def get_last_block(self) -> Optional[Dict]:
        blocks = get_blocks_collection()
        cursor = blocks.find().sort("header.height", -1).limit(1)
        last_block_list = await cursor.to_list(length=1)
        return last_block_list[0] if last_block_list else None

    def _hash_block_header(self, h: BlockHeader) -> str:
        data = f"{h.version}{h.previous_block_hash}{h.merkle_root}{h.timestamp}{h.difficulty_target}{h.nonce}".encode()
        return crypto.sha256_hash(data)

    async def get_block_by_height(self, height: int) -> Optional[Dict]:
        blocks = get_blocks_collection()
        return await blocks.find_one({"header.height": height})

    async def add_block(self, block: Block) -> bool:
        blocks = get_blocks_collection()
        utxos = get_utxos_collection()

        # 1. Check for duplicate block
        if await blocks.find_one({"hash": block.hash}):
            print(f"Block {block.hash} already exists, ignoring.")
            return False

        last_block = await self.get_last_block()

        # 2. Check if the new block creates a fork (is not connected to the current main chain tip)
        if not last_block or block.header.previous_block_hash != last_block['hash']:
            # This is a simplified consensus rule. A full implementation would handle forks.
            print(f"Rejected block {block.hash}: Previous hash does not match current chain tip. Fork detected or orphaned block.")
            return False

        # 3. Check for correct block height
        expected_height = last_block['header']['height'] + 1
        if block.header.height != expected_height:
            print(f"Rejected block {block.hash}: Invalid height. Expected {expected_height}, got {block.header.height}.")
            return False

        height = expected_height

        required_utxo_ids = []
        for tx in block.transactions:
            if not tx.inputs: continue
            for tin in tx.inputs:
                required_utxo_ids.append(f"{tin.transaction_id}:{tin.output_index}")

        utxo_cursor = utxos.find({"_id": {"$in": required_utxo_ids}})
        utxo_snapshot = {u["_id"]: u async for u in utxo_cursor}

        utxos_to_delete = []
        utxos_to_add = []

        for tx in block.transactions:
            if not tx.inputs: continue

            # Create a temporary transaction hash for script validation
            temp_tx_hash_for_validation = crypto.sha256_hash(tx.copy(exclude={'id'}).json().encode())

            for tin in tx.inputs:
                utxo_key = f"{tin.transaction_id}:{tin.output_index}"
                utxo = utxo_snapshot.get(utxo_key)

                if not utxo:
                    print(f"Validation failed: Input UTXO not found for tx {tx.id}")
                    return False

                # --- P2PKH Script Validation ---
                is_valid = crypto.evaluate_p2pkh_script(
                    script_sig=tin.script_sig,
                    script_pub_key=utxo['script_pub_key'],
                    transaction_hash=temp_tx_hash_for_validation
                )
                if not is_valid:
                    print(f"Validation failed: P2PKH script evaluation failed for tx {tx.id}")
                    return False
                # --- End Validation ---

                utxos_to_delete.append(utxo_key)

            for i, tout in enumerate(tx.outputs):
                utxos_to_add.append({"_id": f"{tx.id}:{i}", **tout.dict()})

        coinbase_tx = block.transactions[0]
        for i, tout in enumerate(coinbase_tx.outputs):
            utxos_to_add.append({"_id": f"{coinbase_tx.id}:{i}", **tout.dict()})

        if utxos_to_delete:
            await utxos.delete_many({"_id": {"$in": utxos_to_delete}})
        if utxos_to_add:
            await utxos.insert_many(utxos_to_add)

        await blocks.insert_one(block.dict())
        print(f"Block {height} added to the blockchain.")

        return True

blockchain_instance = Blockchain()
