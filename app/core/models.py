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
    sender_private_key: str = Field(
        ...,
        description="The sender's private key, Base64 encoded.",
        example="LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ1N3b0tQVEVqek9vM2p6eGwKN2dld2d0MUlCMWc0QWhnQUd1QU9ENXN4U0p2blhVZ2dabHhVaXNnWW9qakdKd3p6RnlkMmxrY09Dd1k0WFRvTQprSDd3N1B0S2dZS0tZMjV2a2JFR0NLcUdTTTQ5QXdFSEFEQXdEQVlEVVcwZ0RYNWpkRzl5Y0hWM0xUQXdMelV3CnpRMEZCMFl3TmpJeU1UbGFhR1JqYUNCaVlYUmhZbU5vYjNCbFkzUnBiMjV6WlhKMlpRLS0tLS1FTkQgUFJJVkFIRQotLS0tLQo="
    )
    recipient_address: str = Field(
        ...,
        description="The P2PKH address of the recipient.",
        example="addr_f9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"
    )
    amount: float = Field(
        ...,
        gt=0,
        description="The amount of simulated coin to send.",
        example=10.5
    )
    fee: float = Field(
        0.0,
        ge=0,
        description="The transaction fee to incentivize miners.",
        example=0.001
    )
    lock_height: Optional[int] = Field(
        None,
        description="Optional block height at which this transaction's outputs can be spent (CheckLockTimeVerify).",
        example=150
    )

class MineRequest(BaseModel):
    miner_address: str = Field(
        ...,
        description="The address that will receive the mining reward (coinbase transaction).",
        example="addr_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    )
