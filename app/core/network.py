"""
This file is simplified for a serverless architecture.
In this model, there's no persistent P2P network simulation. The application
interacts directly with a centralized state (the MongoDB database).

The blockchain_instance remains a useful global singleton for interacting
with the blockchain's core logic.
"""

from .blockchain import blockchain_instance

# The concept of a "network" of nodes is removed.
# We now have a single, authoritative blockchain instance.

def get_blockchain_instance():
    return blockchain_instance
