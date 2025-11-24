from pymongo import MongoClient

MONGO_URI = "mongodb+srv://Vercel-Admin-bitcoin:aJPZZhQZyFP7IE4O@bitcoin.27cxupq.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "bitcoin_simulation_v2" # Using a new DB name to avoid conflicts

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
blocks_collection = db["blocks"]
utxos_collection = db["utxos"]

# Exchange Collections
exchange_order_books_collection = db["exchange_order_books"]
exchange_trade_histories_collection = db["exchange_trade_histories"]
exchange_user_balances_collection = db["exchange_user_balances"]
# We are starting simple, other collections will be added back later.

def test_connection():
    try:
        client.admin.command('ping')
        print("MongoDB connection successful.")
        return True
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return False
