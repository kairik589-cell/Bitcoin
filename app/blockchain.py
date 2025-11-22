import time
import hashlib
from typing import Dict, List, Optional

from .models import Block, BlockHeader, Transaction, TransactionInput, TransactionOutput
from . import crypto

# --- Constants ---
GENESIS_BLOCK_HASH = "0" * 64
MINING_REWARD = 50.0

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        # UTXO Set: A dictionary mapping "{tx_id}:{output_index}" to TransactionOutput
        self.utxo_set: Dict[str, TransactionOutput] = {}
        # Mempool: Transactions waiting to be mined
        self.mempool: List[Transaction] = []

        # Create the genesis block
        self._create_genesis_block()

    def _create_genesis_block(self):
        """Creates the very first block in the chain."""
        genesis_tx = Transaction(
            id="genesis_tx_0",
            inputs=[], # Coinbase transactions have no inputs
            outputs=[TransactionOutput(value=MINING_REWARD, script_pub_key="genesis_lock")],
            locktime=0
        )

        genesis_header = BlockHeader(
            previous_block_hash="0",
            merkle_root=crypto.sha256_hash(genesis_tx.id.encode()),
            timestamp=time.time(),
            difficulty_target=1, # Simplified for now
            nonce=0
        )

        genesis_block = Block(
            hash=self._hash_block_header(genesis_header),
            header=genesis_header,
            transactions=[genesis_tx]
        )

        self.chain.append(genesis_block)
        # Add the genesis transaction's output to the UTXO set
        self.utxo_set[f"{genesis_tx.id}:0"] = genesis_tx.outputs[0]

    def get_last_block(self) -> Optional[Block]:
        """Returns the most recent block in the chain."""
        return self.chain[-1] if self.chain else None

    def _hash_block_header(self, header: BlockHeader) -> str:
        """Hashes a block header."""
        header_string = (
            str(header.version) +
            header.previous_block_hash +
            header.merkle_root +
            str(header.timestamp) +
            str(header.difficulty_target) +
            str(header.nonce)
        ).encode()
        return crypto.sha256_hash(header_string)

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """Validates a transaction and adds it to the mempool."""
        if self.validate_transaction(transaction):
            self.mempool.append(transaction)
            return True
        return False

    def validate_transaction(self, transaction: Transaction) -> bool:
        """
        Validates a transaction based on the UTXO model and script execution.
        """
        total_input_value = 0

        # 1. Verify all inputs exist and scripts are valid
        for tx_input in transaction.inputs:
            utxo_key = f"{tx_input.transaction_id}:{tx_input.output_index}"

            # Check if the referenced output is in the current UTXO set
            if utxo_key not in self.utxo_set:
                print(f"Error: Referenced UTXO {utxo_key} not found or already spent.")
                return False

            utxo = self.utxo_set[utxo_key]

            # Execute the script to see if the spender is authorized
            is_valid_spend = crypto.execute_script(
                script_sig=tx_input.script_sig,
                script_pub_key=utxo.script_pub_key,
                transaction_hash=transaction.id # The hash of the current tx is signed
            )

            if not is_valid_spend:
                print(f"Error: Script validation failed for UTXO {utxo_key}.")
                return False

            total_input_value += utxo.value

        # 2. Verify that the input value is not less than the output value
        total_output_value = sum(tx_output.value for tx_output in transaction.outputs)

        if total_input_value < total_output_value:
            print("Error: Input value is less than output value (insufficient funds).")
            return False

        # Note: The difference (total_input_value - total_output_value) is the transaction fee.

        # 3. Check for double-spending within the same transaction
        if len(set(f"{i.transaction_id}:{i.output_index}" for i in transaction.inputs)) != len(transaction.inputs):
             print("Error: Transaction contains double-spent inputs.")
             return False

        return True

    def add_block(self, block: Block) -> bool:
        """
        Adds a new block to the chain after validation.
        """
        last_block = self.get_last_block()
        if not last_block:
            return False

        # 1. Validate block header
        if block.header.previous_block_hash != last_block.hash:
            return False # Doesn't chain to the last block

        # (Proof-of-Work validation will be added in the mining step)

        # 2. Validate all transactions in the block
        for tx in block.transactions:
            # Coinbase tx is special
            if not tx.inputs:
                continue
            if not self.validate_transaction(tx):
                return False

        # 3. Add the block to the chain
        self.chain.append(block)

        # 4. Update the UTXO set
        for tx in block.transactions:
            # Remove spent outputs from the UTXO set
            for tx_input in tx.inputs:
                utxo_key = f"{tx_input.transaction_id}:{tx_input.output_index}"
                if utxo_key in self.utxo_set:
                    del self.utxo_set[utxo_key]

            # Add new unspent outputs to the UTXO set
            for i, tx_output in enumerate(tx.outputs):
                utxo_key = f"{tx.id}:{i}"
                self.utxo_set[utxo_key] = tx_output

        return True

    def validate_chain(self) -> bool:
        """
        Validates the integrity of the entire blockchain.
        - Checks previous block hashes.
        - Checks the hash of each block's header.
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # 1. Check if the previous_block_hash pointer is correct
            if current_block.header.previous_block_hash != previous_block.hash:
                print(f"Chain validation failed: Previous hash mismatch at block {i}.")
                return False

            # 2. Check if the block's own hash is valid
            if current_block.hash != self._hash_block_header(current_block.header):
                print(f"Chain validation failed: Block hash is incorrect at block {i}.")
                return False

        # (A more thorough validation would also re-validate every transaction)

        return True


# A single, shared instance of the blockchain (in-memory database)
blockchain_instance = Blockchain()
