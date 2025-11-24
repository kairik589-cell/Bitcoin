from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time
import uuid

from app.core.database import (
    get_exchange_order_books_collection,
    get_exchange_trade_histories_collection,
    get_exchange_user_balances_collection
)

router = APIRouter(prefix="/exchange", tags=["Exchange (DB)"])

# --- Models ---
class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    order_type: str = Field(..., pattern="^(bid|ask)$")
    price: float = Field(..., gt=0)
    amount: float = Field(..., gt=0)
    coin_pair: str
    timestamp: float = Field(default_factory=time.time)

class Deposit(BaseModel):
    user_id: str
    amount: float
    coin: str

# --- Helper Functions ---
async def _execute_trade(buyer_id: str, seller_id: str, price: float, amount: float, pair: str):
    balances = get_exchange_user_balances_collection()
    trades = get_exchange_trade_histories_collection()
    base, quote = pair.split('/')

    await balances.update_one({"_id": buyer_id}, {"$inc": {quote: -amount * price, base: amount}}, upsert=True)
    await balances.update_one({"_id": seller_id}, {"$inc": {base: -amount, quote: amount * price}}, upsert=True)

    trade = {"price": price, "amount": amount, "timestamp": time.time(), "buyer": buyer_id, "seller": seller_id, "pair": pair}
    await trades.insert_one(trade)

async def match_orders(pair: str):
    order_books = get_exchange_order_books_collection()
    book = await order_books.find_one({"_id": pair})

    book['bids'].sort(key=lambda x: x['price'], reverse=True)
    book['asks'].sort(key=lambda x: x['price'])

    while book["bids"] and book["asks"] and book["bids"][0]['price'] >= book["asks"][0]['price']:
        bid, ask = book["bids"][0], book["asks"][0]
        trade_amount = min(bid['amount'], ask['amount'])

        await _execute_trade(bid['user_id'], ask['user_id'], ask['price'], trade_amount, pair)

        bid['amount'] -= trade_amount
        ask['amount'] -= trade_amount

        if bid['amount'] == 0: book["bids"].pop(0)
        if ask['amount'] == 0: book["asks"].pop(0)

    await order_books.update_one({"_id": pair}, {"$set": {"bids": book["bids"], "asks": book["asks"]}})

# --- API Endpoints ---
@router.post("/order", summary="Place an Order")
async def place_order(order: Order):
    order_books = get_exchange_order_books_collection()
    balances = get_exchange_user_balances_collection()

    if not await order_books.find_one({"_id": order.coin_pair}):
        raise HTTPException(404, "Market not found.")

    # --- Balance Check ---
    user_balance = await balances.find_one({"_id": order.user_id}) or {}
    base, quote = order.coin_pair.split('/')

    if order.order_type == "bid":
        required_balance = order.price * order.amount
        if user_balance.get(quote, 0) < required_balance:
            raise HTTPException(400, f"Insufficient {quote} balance.")
    else: # ask
        required_balance = order.amount
        if user_balance.get(base, 0) < required_balance:
            raise HTTPException(400, f"Insufficient {base} balance.")
    # --- End Balance Check ---

    order_dict = order.dict()
    update_field = "bids" if order.order_type == "bid" else "asks"
    await order_books.update_one({"_id": order.coin_pair}, {"$push": {update_field: order_dict}})

    await match_orders(order.coin_pair)
    return {"message": "Order placed and matching attempted.", "order_id": order.id}

@router.get("/orderbook/{pair}", summary="Get Order Book")
async def get_order_book(pair: str):
    order_books = get_exchange_order_books_collection()
    book = await order_books.find_one({"_id": pair}, {"_id": 0})
    if not book: raise HTTPException(404, "Market not found.")
    return book

@router.post("/deposit", summary="Deposit Currency")
async def deposit(d: Deposit):
    balances = get_exchange_user_balances_collection()
    await balances.update_one({"_id": d.user_id}, {"$inc": {d.coin: d.amount}}, upsert=True)
    return {"message": "Deposit successful."}

@router.get("/balances/{user_id}", summary="Get User Balances")
async def get_balances(user_id: str):
    balances = get_exchange_user_balances_collection()
    user_balances = await balances.find_one({"_id": user_id}, {"_id": 0})
    return user_balances or {}
