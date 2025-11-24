import motor.motor_asyncio
from app.core.config import settings

# Global client and db variables
client: motor.motor_asyncio.AsyncIOMotorClient = None
db = None

async def connect_to_mongo():
    global client, db
    client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_DETAILS)
    db = client[settings.DATABASE_NAME]
    print("Connected to MongoDB.")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")

def get_db():
    if db is None:
        raise Exception("Database not initialized. Call connect_to_mongo first.")
    return db

# We will define collections here for easy access, but they will be accessed via get_db()
def get_blocks_collection():
    return get_db()["blocks"]

def get_utxos_collection():
    return get_db()["utxos"]

def get_mempool_collection():
    return get_db()["mempool"]

# Exchange Collections
def get_exchange_order_books_collection():
    return get_db()["exchange_order_books"]

def get_exchange_trade_histories_collection():
    return get_db()["exchange_trade_histories"]

def get_exchange_user_balances_collection():
    return get_db()["exchange_user_balances"]
