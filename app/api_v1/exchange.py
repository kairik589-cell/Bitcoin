from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time

from app.database import (
    exchange_order_books_collection as order_books,
    exchange_trade_histories_collection as trade_histories,
    exchange_user_balances_collection as user_balances,
)

router = APIRouter(prefix="/exchange", tags=["Exchange (DB)"])

# Initialize default market in DB if it doesn't exist
if order_books.count_documents({"_id": "SIM_COIN/USD"}) == 0:
    order_books.insert_one({"_id": "SIM_COIN/USD", "bids": [], "asks": []})

# Models
class Order(BaseModel):
    user_id: str
    order_type: str = Field(..., pattern="^(bid|ask)$")
    price: float = Field(..., gt=0)
    amount: float = Field(..., gt=0)
    coin_pair: str

class Deposit(BaseModel):
    user_id: str
    amount: float
    coin: str

def _execute_trade(buyer_id, seller_id, price, amount, pair):
    base, quote = pair.split('/')
    user_balances.update_one({"_id": buyer_id}, {"$inc": {quote: -amount * price, base: amount}}, upsert=True)
    user_balances.update_one({"_id": seller_id}, {"$inc": {base: -amount, quote: amount * price}}, upsert=True)
    trade = {"price": price, "amount": amount, "timestamp": time.time(), "buyer": buyer_id, "seller": seller_id, "pair": pair}
    trade_histories.insert_one(trade)

def match_orders(pair: str):
    book = order_books.find_one({"_id": pair})

    while book["bids"] and book["asks"] and book["bids"][0]['price'] >= book["asks"][0]['price']:
        bid, ask = book["bids"][0], book["asks"][0]
        trade_amount = min(bid['amount'], ask['amount'])

        _execute_trade(bid['user_id'], ask['user_id'], ask['price'], trade_amount, pair)

        bid['amount'] -= trade_amount
        ask['amount'] -= trade_amount
        if bid['amount'] == 0: book["bids"].pop(0)
        if ask['amount'] == 0: book["asks"].pop(0)

    order_books.update_one({"_id": pair}, {"$set": {"bids": book["bids"], "asks": book["asks"]}})

@router.post("/order", summary="Place an Order")
def place_order(order: Order):
    if not order_books.find_one({"_id": order.coin_pair}):
        raise HTTPException(404, "Market not found.")

    # Balance check
    # ...

    book = order_books.find_one({"_id": order.coin_pair})
    if order.order_type == "bid":
        book["bids"].append(order.dict()); book["bids"].sort(key=lambda x: x['price'], reverse=True)
    else:
        book["asks"].append(order.dict()); book["asks"].sort(key=lambda x: x['price'])
    order_books.update_one({"_id": order.coin_pair}, {"$set": {"bids": book["bids"], "asks": book["asks"]}})

    match_orders(order.coin_pair)
    return {"message": "Order placed and matching attempted."}

@router.get("/orderbook/{pair}", summary="Get Order Book")
def get_order_book(pair: str):
    book = order_books.find_one({"_id": pair}, {"_id": 0})
    if not book: raise HTTPException(404, "Market not found.")
    return book

@router.post("/deposit", summary="Deposit")
def deposit(d: Deposit):
    user_balances.update_one({"_id": d.user_id}, {"$inc": {d.coin: d.amount}}, upsert=True)
    return {"message": "Deposit successful."}

@router.get("/balances/{user_id}", summary="Get Balances")
def get_balances(user_id: str):
    balances = user_balances.find_one({"_id": user_id}, {"_id": 0})
    return balances or {}
