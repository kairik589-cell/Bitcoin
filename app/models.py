from pydantic import BaseModel, Field
from typing import List, Optional

class TransactionInput(BaseModel):
    transaction_id: str
    output_index: int
    script_sig: str

class TransactionOutput(BaseModel):
    value: float
    script_pub_key: str
    lock_height: Optional[int] = None

class Transaction(BaseModel):
    id: str
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
    height: int

class Block(BaseModel):
    hash: str
    header: BlockHeader
    transactions: List[Transaction]

# --- API Models ---
class TransactionCreateRequest(BaseModel):
    sender_private_key: str
    recipient_address: str
    amount: float
    fee: float = 0.0
    lock_height: Optional[int] = None

class MineRequest(BaseModel):
    miner_address: str
