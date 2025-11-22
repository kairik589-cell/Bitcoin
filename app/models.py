from pydantic import BaseModel, Field
from typing import List, Optional

class TransactionInput(BaseModel):
    """
    Represents a reference to a previous transaction's output (UTXO).
    """
    transaction_id: str = Field(..., description="The ID of the transaction containing the output to be spent.")
    output_index: int = Field(..., description="The index of the output in the referenced transaction.")
    script_sig: str = Field(..., description="The unlocking script (e.g., signature and public key).")

class TransactionOutput(BaseModel):
    """
    Represents an amount of currency and the condition (script) to spend it.
    """
    value: float = Field(..., description="The value of the output in a satoshi-like unit.")
    script_pub_key: str = Field(..., description="The locking script (e.g., Pay-to-Public-Key-Hash).")

class Transaction(BaseModel):
    """
    Represents a transfer of value from inputs to outputs.
    """
    id: str = Field(..., description="The unique identifier (hash) of this transaction.")
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    locktime: int = 0

class BlockHeader(BaseModel):
    """
    Represents the header of a block in the blockchain.
    """
    version: int = 1
    previous_block_hash: str
    merkle_root: str
    timestamp: float
    difficulty_target: int
    nonce: int

class Block(BaseModel):
    """
    Represents a full block, containing the header and all transactions.
    """
    hash: str = Field(..., description="The unique identifier (hash) of this block.")
    header: BlockHeader
    transactions: List[Transaction]

# --- API Specific Models ---

class WalletCreateResponse(BaseModel):
    """
    Response model for the wallet creation endpoint.
    """
    private_key: str = Field(..., description="The private key (serialized, base64). Keep this secret!")
    public_key: str = Field(..., description="The public key (serialized, base64).")
    address: str = Field(..., description="The P2PKH address derived from the public key.")

class TransactionCreateRequest(BaseModel):
    """
    Request model for creating a new transaction.
    """
    sender_private_key: str
    recipient_address: str
    amount: float
    fee: float = 0.0

class MineRequest(BaseModel):
    """
    Request model for the mining endpoint.
    """
    miner_address: str
