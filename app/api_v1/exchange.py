from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from typing import List, Dict

router = APIRouter(
    prefix="/exchange",
    tags=["Exchange v1"],
)

# --- In-Memory Order Book ---
# A simple list to store buy and sell orders.
# In a real system, this would be a database and a more complex matching engine.
order_book = {
    "bids": [], # Buy orders
    "asks": []  # Sell orders
}

# --- Models ---
class Order(BaseModel):
    user_id: str
    order_type: str = Field(..., pattern="^(bid|ask)$") # bid (buy) or ask (sell)
    price: float = Field(..., gt=0)
    amount: float = Field(..., gt=0)

# --- Endpoints ---

@router.get("/orderbook", summary="Get the Current Order Book")
def get_order_book():
    """
    Retrieves the current state of the order book, showing all buy (bids)
    and sell (asks) orders.
    """
    return order_book

@router.post("/order", summary="Place a New Order")
def place_order(order: Order = Body(...)):
    """
    Places a new buy (bid) or sell (ask) order into the order book.
    (Note: This simple implementation does not include an order matching engine.)
    """
    if order.order_type == "bid":
        order_book["bids"].append(order.dict())
        # Sort bids from highest price to lowest
        order_book["bids"].sort(key=lambda x: x['price'], reverse=True)
    elif order.order_type == "ask":
        order_book["asks"].append(order.dict())
        # Sort asks from lowest price to highest
        order_book["asks"].sort(key=lambda x: x['price'])

    return {"message": "Order placed successfully", "order": order}
