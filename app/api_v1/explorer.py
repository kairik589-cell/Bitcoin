from fastapi import APIRouter, HTTPException
from typing import List

from app.core.models import Block, Transaction
from app.core.blockchain import blockchain_instance
from app.core.database import get_blocks_collection

router = APIRouter(prefix="/explorer", tags=["Blockchain Explorer"])

@router.get("/block/height/{height}", response_model=Block, summary="Get Block by Height")
async def get_block_by_height(height: int):
    """
    Retrieves a full block from the blockchain by its height.
    """
    block = await blockchain_instance.get_block_by_height(height)
    if not block:
        raise HTTPException(status_code=404, detail=f"Block with height {height} not found.")
    return block

@router.get("/transaction/{tx_id}", response_model=Transaction, summary="Get Transaction by ID")
async def get_transaction_by_id(tx_id: str):
    """
    Finds and retrieves a transaction by its ID from the entire blockchain.
    Note: This can be slow as it scans all blocks. A real explorer would index transactions.
    """
    blocks = get_blocks_collection()
    pipeline = [
        {"$unwind": "$transactions"},
        {"$match": {"transactions.id": tx_id}},
        {"$replaceRoot": {"newRoot": "$transactions"}}
    ]

    cursor = blocks.aggregate(pipeline)
    transaction_list = await cursor.to_list(length=1)

    if not transaction_list:
        raise HTTPException(status_code=404, detail=f"Transaction with ID '{tx_id}' not found.")

    return transaction_list[0]
