from typing import List, Dict
from copy import deepcopy
import random

from .blockchain import Blockchain
from .models import Transaction, Block
from .mining import mine_new_block
from .database import utxos_collection

# A single, shared, stateless manager that interacts with the DB
blockchain_manager = Blockchain()

class Node:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.mempool: List[Transaction] = []

    def add_transaction(self, tx: Transaction):
        self.mempool.append(tx)

    def mine_block(self, miner_address: str) -> Block:
        last_block = blockchain_manager.get_last_block()
        chain_for_mining = [last_block] if last_block else []

        current_utxos = {utxo['_id']: utxo for utxo in utxos_collection.find()}

        new_block = mine_new_block(
            mempool=self.mempool,
            utxo_set=current_utxos,
            chain=chain_for_mining,
            miner_address=miner_address
        )
        self.mempool = [tx for tx in self.mempool if tx.id not in {t.id for t in new_block.transactions}]
        return new_block

    def receive_block(self, block: Block) -> bool:
        if blockchain_manager.add_block(block):
            tx_ids_in_block = {tx.id for tx in block.transactions}
            self.mempool = [tx for tx in self.mempool if tx.id not in tx_ids_in_block]
            return True
        return False

class Network:
    def __init__(self, num_nodes: int):
        self.nodes: Dict[str, Node] = {f"node_{i}": Node(f"node_{i}") for i in range(num_nodes)}
        self.blockchain_manager = blockchain_manager # Add this line

    def broadcast_transaction(self, tx: Transaction):
        for node in self.nodes.values():
            node.add_transaction(deepcopy(tx))

    def broadcast_block(self, new_block: Block, origin_node_id: str):
        for node_id, node in self.nodes.items():
            if node_id != origin_node_id:
                node.receive_block(deepcopy(new_block))

    def get_random_node(self) -> Node:
        return random.choice(list(self.nodes.values()))

network_instance = Network(num_nodes=3)
