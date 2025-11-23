from pydantic import BaseModel, Field
from typing import List, Optional

class TransactionInput(BaseModel):
    transaction_id: str = Field(..., description="The ID of the transaction containing the output to be spent.")
    output_index: int = Field(..., description="The index of the output in the referenced transaction.")
    script_sig: str = Field(..., description="The unlocking script (e.g., signature and public key).")

class TransactionOutput(BaseModel):
    value: float = Field(..., description="The value of the output in a satoshi-like unit.")
    script_pub_key: str = Field(..., description="The locking script (e.g., Pay-to-Public-Key-Hash).")

class Transaction(BaseModel):
    id: str = Field(..., description="The unique identifier (hash) of this transaction.")
    inputs: List[TransactionInput]
    outputs: List[TransactionOutput]
    locktime: int = 0

class BlockHeader(BaseModel):
    version: int = 1
    previous_block_hash: str
    merkle_root: str
    timestamp: float
    difficulty_target: int
    nonce: int

class Block(BaseModel):
    hash: str = Field(..., description="The unique identifier (hash) of this block.")
    header: BlockHeader
    # A block can now contain different types of transactions.
    # In a real implementation, this would use a more robust system.
    transactions: List[Transaction]
    # For now, we'll handle token transactions separately in the blockchain logic.

# --- API Specific Models ---

class WalletCreateResponse(BaseModel):
    private_key: str = Field(..., description="The private key (serialized, base64). Keep this secret!")
    public_key: str = Field(..., description="The public key (serialized, base64).")
    address: str = Field(..., description="The P2PKH address derived from the public key.")

class TransactionCreateRequest(BaseModel):
    sender_private_key: str
    recipient_address: str
    amount: float
    fee: float = 0.0

class MineRequest(BaseModel):
    miner_address: str

class MultiSigWalletCreateRequest(BaseModel):
    public_keys_b64: List[str]
    required_signatures: int

class MultiSigWalletCreateResponse(BaseModel):
    multisig_address: str
    redeem_script: str

# --- Custom Token Models ---

class TokenTransaction(BaseModel):
    id: str
    fee_inputs: List[TransactionInput]
    fee_outputs: List[TransactionOutput] # For change

class TokenIssuanceTransaction(TokenTransaction):
    token_id: str
    token_name: str
    total_supply: float
    issuer: str

class TokenTransferTransaction(TokenTransaction):
    token_id: str
    sender: str
    recipient: str
    amount: float

# --- Token API Request Models ---

class TokenIssuanceRequest(BaseModel):
    issuer_private_key: str
    token_id: str
    token_name: str
    total_supply: float
    fee: float

class TokenTransferRequest(BaseModel):
    sender_private_key: str
    token_id: str
    recipient_address: str
    amount: float
    fee: float
