from fastapi import APIRouter, Body, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time, json, asyncio
from app.network import network_instance

router = APIRouter(prefix="/exchange", tags=["Exchange v1"])

# WebSocket Manager
class ConnectionManager:
    def __init__(self): self.active_connections: List[WebSocket] = []
    async def connect(self, ws: WebSocket): await ws.accept(); self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket): self.active_connections.remove(ws)
    async def broadcast(self, msg: str):
        for conn in self.active_connections: await conn.send_text(msg)
manager = ConnectionManager()

# In-Memory State for multiple markets
order_books: Dict[str, Dict[str, List]] = {"SIM_COIN/USD": {"bids": [], "asks": []}}
user_balances: Dict[str, Dict[str, float]] = {}
trade_histories: Dict[str, List[Dict]] = {"SIM_COIN/USD": []}

# Models
class Order(BaseModel):
    user_id: str; order_type: str = Field(..., pattern="^(bid|ask)$"); price: Optional[float] = Field(None, gt=0); amount: float = Field(..., gt=0); coin_pair: str
class Deposit(BaseModel):
    user_id: str; amount: float = Field(..., gt=0); coin: str
class Withdrawal(BaseModel):
    user_id: str; amount: float = Field(..., gt=0); coin: str; recipient_address: Optional[str] = None
class CreateMarketRequest(BaseModel):
    base_coin: str; quote_coin: str

# Matching Engine (now market-aware)
def _execute_trade(buyer_id, seller_id, price, amount, pair):
    base_coin, quote_coin = pair.split('/')
    user_balances[buyer_id][quote_coin] -= amount * price
    user_balances[buyer_id][base_coin] = user_balances[buyer_id].get(base_coin, 0) + amount
    user_balances[seller_id][base_coin] -= amount
    user_balances[seller_id][quote_coin] = user_balances[seller_id].get(quote_coin, 0) + amount * price
    trade = {"price": price, "amount": amount, "timestamp": time.time(), "buyer_id": buyer_id, "seller_id": seller_id}
    trade_histories[pair].append(trade)
    return trade

def match_limit_orders(pair: str):
    trades = []
    book = order_books[pair]
    while book["bids"] and book["asks"]:
        bid, ask = book["bids"][0], book["asks"][0]
        if bid['price'] >= ask['price']:
            trade_price = ask['price']
            trade_amount = min(bid['amount'], ask['amount'])
            trade = _execute_trade(bid['user_id'], ask['user_id'], trade_price, trade_amount, pair)
            trades.append(trade)
            bid['amount'] -= trade_amount
            ask['amount'] -= trade_amount
            if bid['amount'] == 0: book["bids"].pop(0)
            if ask['amount'] == 0: book["asks"].pop(0)
        else:
            break
    if trades:
        asyncio.create_task(manager.broadcast(json.dumps({"type": "new_trades", "pair": pair, "data": trades})))
    return trades

# Endpoints
@router.websocket("/ws/trades")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive by waiting for data (optional)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
@router.post("/order", summary="Place a New Order")
def place_order(order: Order = Body(...)):
    if order.coin_pair not in order_books: raise HTTPException(status_code=404, detail="Market does not exist.")
    if order.price is None: return handle_market_order(order)
    else: return handle_limit_order(order)

def handle_limit_order(order: Order):
    user_id, pair = order.user_id, order.coin_pair
    base_coin, quote_coin = pair.split('/')
    if user_id not in user_balances: raise HTTPException(status_code=400, detail="User has no account.")

    if order.order_type == "bid":
        if user_balances[user_id].get(quote_coin, 0) < order.amount * order.price: raise HTTPException(status_code=400, detail=f"Insufficient {quote_coin}.")
    else:
        if user_balances[user_id].get(base_coin, 0) < order.amount: raise HTTPException(status_code=400, detail=f"Insufficient {base_coin}.")

    book = order_books[pair]
    if order.order_type == "bid":
        book["bids"].append(order.dict()); book["bids"].sort(key=lambda x: x['price'], reverse=True)
    else:
        book["asks"].append(order.dict()); book["asks"].sort(key=lambda x: x['price'])

    trades = match_limit_orders(pair)
    return {"message": "Limit order placed.", "trades_executed": trades}

def handle_market_order(order: Order):
    trades = []
    amount_to_fill, user_id, pair = order.amount, order.user_id, order.coin_pair
    base_coin, quote_coin = pair.split('/')
    book = order_books[pair]

    if order.order_type == "bid":
        if not book["asks"]: raise HTTPException(status_code=400, detail="No sellers.")
        for ask in list(book["asks"]):
            if amount_to_fill <= 0: break
            trade_amount = min(amount_to_fill, ask['amount'])
            required_quote = trade_amount * ask['price']
            if user_balances.get(user_id, {}).get(quote_coin, 0) < required_quote: break
            trade = _execute_trade(user_id, ask['user_id'], ask['price'], trade_amount, pair)
            trades.append(trade)
            amount_to_fill -= trade_amount
            ask['amount'] -= trade_amount
            if ask['amount'] == 0: book["asks"].remove(ask)
    else:
        if not book["bids"]: raise HTTPException(status_code=400, detail="No buyers.")
        if user_balances.get(user_id, {}).get(base_coin, 0) < amount_to_fill: raise HTTPException(status_code=400, detail=f"Insufficient {base_coin}.")
        for bid in list(book["bids"]):
            if amount_to_fill <= 0: break
            trade_amount = min(amount_to_fill, bid['amount'])
            trade = _execute_trade(bid['user_id'], user_id, bid['price'], trade_amount, pair)
            trades.append(trade)
            amount_to_fill -= trade_amount
            bid['amount'] -= trade_amount
            if bid['amount'] == 0: book["bids"].remove(bid)

    if not trades: raise HTTPException(status_code=400, detail="Could not fill order.")
    if trades: asyncio.create_task(manager.broadcast(json.dumps({"type": "new_trades", "pair": pair, "data": trades})))
    return {"message": "Market order executed.", "trades_executed": trades}

@router.get("/orderbook/{coin_pair}", summary="Get Order Book")
def get_order_book(coin_pair: str):
    if coin_pair not in order_books: raise HTTPException(status_code=404, detail="Market not found.")
    return order_books[coin_pair]
@router.get("/trades/{coin_pair}", summary="Get Recent Trades")
def get_trades(coin_pair: str):
    if coin_pair not in trade_histories: raise HTTPException(status_code=404, detail="Market not found.")
    return trade_histories[coin_pair][-50:]
@router.get("/balances/{user_id}", summary="Get Balances")
def get_balances(user_id: str): return {"balances": user_balances.get(user_id, {})}
@router.post("/deposit", summary="Deposit")
def deposit(d: Deposit):
    if d.user_id not in user_balances: user_balances[d.user_id] = {}
    user_balances[d.user_id][d.coin] = user_balances[d.user_id].get(d.coin, 0) + d.amount
    return {"message": "Deposit successful"}
@router.post("/withdraw", summary="Withdraw")
def withdraw(w: Withdrawal):
    if user_balances.get(w.user_id, {}).get(w.coin, 0) < w.amount: raise HTTPException(status_code=400, detail="Insufficient funds.")
    user_balances[w.user_id][w.coin] -= w.amount
    return {"message": "Withdrawal processed"}
@router.post("/markets", summary="Create Market")
def create_market(request: CreateMarketRequest):
    pair = f"{request.base_coin}/{request.quote_coin}"
    if pair in order_books: raise HTTPException(status_code=400, detail="Market exists.")
    node = network_instance.get_random_node()
    if request.base_coin not in node.blockchain.token_definitions and request.base_coin != "SIM_COIN":
        raise HTTPException(status_code=404, detail="Token not found.")
    order_books[pair], trade_histories[pair] = {"bids": [], "asks": []}, []
    return {"message": "Market created", "market": pair}
