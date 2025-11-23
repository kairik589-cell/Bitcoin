from typing import List, Dict
from copy import deepcopy
import random

from .blockchain import Blockchain
from .models import Transaction, Block
from .mining import mine_new_block

class Node:
    """Represents a single node (or miner) in the simulated network."""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.blockchain = Blockchain()
        # Each node has its own mempool
        self.mempool: List[Transaction] = []
        self.token_mempool: List = []

    def add_transaction(self, tx: Transaction):
        # In a real network, this would be validated before adding.
        # Here we assume validation happens at the network level.
        self.mempool.append(tx)

    def mine_block(self, miner_address: str) -> Block:
        """Mines a new block based on the node's current blockchain state."""
        new_block = mine_new_block(
            mempool=self.mempool,
            utxo_set=self.blockchain.utxo_set,
            chain=self.blockchain.chain,
            miner_address=miner_address
        )
        # Clear mempools after mining
        self.mempool.clear()
        self.token_mempool.clear()
        return new_block

    def receive_block(self, block: Block) -> bool:
        """
        Receives a block from the network, validates it, and potentially adds it.
        This is where the consensus logic (longest chain rule) applies.
        """
        last_local_block = self.blockchain.get_last_block()

        # 1. Check if the new block's chain is longer than ours
        # (A simple proxy for this is checking if it connects to our head)
        if block.header.previous_block_hash == last_local_block.hash:
            if self.blockchain.add_block(block):
                # Block was valid and added successfully
                return True

        # TODO: Implement full chain replacement logic for forks.
        # If block.height > self.blockchain.height, the node would request
        # the full chain from the sender and validate it.

        return False


class Network:
    """Manages all nodes in the simulated P2P network."""
    def __init__(self, num_nodes: int):
        self.nodes: Dict[str, Node] = {f"node_{i}": Node(f"node_{i}") for i in range(num_nodes)}

    def broadcast_transaction(self, tx: Transaction):
        """Sends a new transaction to all nodes in the network."""
        for node in self.nodes.values():
            node.add_transaction(deepcopy(tx))

    def broadcast_block(self, new_block: Block, origin_node_id: str):
        """Sends a newly mined block to all other nodes."""
        for node_id, node in self.nodes.items():
            if node_id != origin_node_id:
                node.receive_block(deepcopy(new_block))

    def get_random_node(self) -> Node:
        """Returns a random node from the network to interact with."""
        return random.choice(list(self.nodes.values()))

# A single, shared instance of the network
network_instance = Network(num_nodes=3)
