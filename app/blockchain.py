import time
import hashlib
from typing import Dict, List, Optional

from .models import (
    Block, BlockHeader, Transaction, TransactionInput, TransactionOutput,
    TokenIssuanceTransaction, TokenTransferTransaction
)
from . import crypto

# --- Constants and Protocol Rules ---
GENESIS_BLOCK_HASH = "0" * 64
INITIAL_MINING_REWARD = 50.0
HALVING_INTERVAL = 10 # blocks

def calculate_mining_reward(block_height: int) -> float:
    """
    Calculates the mining reward based on the block height,
    simulating a halving event every HALVING_INTERVAL blocks.
    """
    halvings = block_height // HALVING_INTERVAL
    return INITIAL_MINING_REWARD / (2 ** halvings)

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.utxo_set: Dict[str, TransactionOutput] = {}
        self.mempool: List[Transaction] = []
        self.token_mempool: List = [] # Will hold TokenIssuanceTransaction or TokenTransferTransaction

        # --- Custom Token State ---
        # Stores the definition of each token
        self.token_definitions: Dict[str, dict] = {} # token_id -> {details}
        # Stores the balance of each token for each user
        self.token_balances: Dict[str, Dict[str, float]] = {} # user_address -> {token_id: balance}

        self._create_genesis_block()

    def _create_genesis_block(self):
        """Creates the very first block in the chain."""
        reward = calculate_mining_reward(0)
        genesis_tx = Transaction(
            id="genesis_tx_0",
            inputs=[], # Coinbase transactions have no inputs
            outputs=[TransactionOutput(value=reward, script_pub_key="genesis_lock")],
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

        # 4. Update the UTXO set for native coin transactions
        for tx in block.transactions:
            for tx_input in tx.inputs:
                utxo_key = f"{tx_input.transaction_id}:{tx_input.output_index}"
                if utxo_key in self.utxo_set: del self.utxo_set[utxo_key]
            for i, tx_output in enumerate(tx.outputs):
                self.utxo_set[f"{tx.id}:{i}"] = tx_output

        # 5. Process token transactions from the token_mempool
        for tx in self.token_mempool:
            # Update UTXO set for fee payments
            for fee_input in tx.fee_inputs:
                utxo_key = f"{fee_input.transaction_id}:{fee_input.output_index}"
                if utxo_key in self.utxo_set: del self.utxo_set[utxo_key]
            for i, fee_output in enumerate(tx.fee_outputs):
                self.utxo_set[f"{tx.id}:{i}"] = fee_output # Using token tx id for simplicity

            # Update token state
            if isinstance(tx, TokenIssuanceTransaction):
                self.token_definitions[tx.token_id] = tx.dict(exclude={'id', 'fee_inputs', 'fee_outputs'})
                self.token_balances[tx.issuer] = {tx.token_id: tx.total_supply}

            elif isinstance(tx, TokenTransferTransaction):
                # Debit sender
                self.token_balances[tx.sender][tx.token_id] -= tx.amount
                # Credit recipient
                if tx.recipient not in self.token_balances: self.token_balances[tx.recipient] = {}
                self.token_balances[tx.recipient][tx.token_id] = self.token_balances[tx.recipient].get(tx.token_id, 0) + tx.amount

        # 6. Clear the token mempool
        self.token_mempool.clear()

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

    # --- Token Transaction Validation ---

    def _validate_fee_payment(self, fee_inputs: List[TransactionInput], fee_outputs: List[TransactionOutput]) -> bool:
        """Helper to validate the fee portion of a token transaction."""
        total_input = sum(self.utxo_set[f"{i.transaction_id}:{i.output_index}"].value for i in fee_inputs)
        total_output = sum(o.value for o in fee_outputs)
        return total_input >= total_output # Fee is the difference

    def validate_token_issuance(self, tx: TokenIssuanceTransaction) -> bool:
        """Validates a new token issuance transaction."""
        # 1. Check if token ID already exists
        if tx.token_id in self.token_definitions:
            return False
        # 2. Validate the fee payment
        if not self._validate_fee_payment(tx.fee_inputs, tx.fee_outputs):
            return False
        return True

    def validate_token_transfer(self, tx: TokenTransferTransaction) -> bool:
        """Validates a token transfer transaction."""
        # 1. Check if token exists
        if tx.token_id not in self.token_definitions:
            return False
        # 2. Check if sender has enough token balance
        sender_balance = self.token_balances.get(tx.sender, {}).get(tx.token_id, 0)
        if sender_balance < tx.amount:
            return False
        # 3. Validate the fee payment
        if not self._validate_fee_payment(tx.fee_inputs, tx.fee_outputs):
            return False
        return True

    def process_token_transactions(self, block: Block):
        """Processes token transactions in a block to update state."""
        # This is a conceptual simplification. We're assuming token tx are passed separately.
        # A real implementation would embed them in the block's transaction list.

        # In this simulation, we'll have to pass token tx to `add_block` separately.
        # This is a limitation of not redesigning the Block model fundamentally.
        pass # Logic will be handled in `add_block` for now.

# A single, shared instance of the blockchain (in-memory database)
blockchain_instance = Blockchain()
