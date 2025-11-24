# Bitcoin Simulation API

This project is a comprehensive, feature-rich simulation of a Bitcoin-like system, built as a centralized API using Python and the FastAPI framework. It is designed for educational purposes and is optimized for serverless deployment on Vercel.

## Core Features

The simulation implements many of the core concepts of the Bitcoin protocol:

- **UTXO Model:** The blockchain uses an Unspent Transaction Output model for tracking value.
- **P2PKH Scripting:** Transactions are secured using Pay-to-Public-Key-Hash (P2PKH) script validation, ensuring only valid owners can spend outputs.
- **Proof-of-Work:** New blocks are created through a Proof-of-Work mining process.
- **Difficulty Adjustment:** The mining difficulty automatically adjusts every 20 blocks to maintain a stable target block time.
- **Economic Model:** The simulation includes transaction fees for miners and a "Halving" event that reduces the block reward every 50 blocks.
- **Merkle Trees:** Each block contains a Merkle root, providing an efficient way to verify transaction inclusion.

## Serverless Architecture

This application is specifically designed for a serverless environment like Vercel, which has important architectural implications:

- **Stateless Application:** The API itself is stateless. It does not maintain any state (like a mempool or network connections) in memory between requests.
- **Centralized State on MongoDB:** All persistent state—including the blockchain, the UTXO set, and the mempool of pending transactions—is stored in a MongoDB Atlas database. This makes the application robust and scalable.
- **No P2P Simulation:** Due to the stateless nature of serverless functions, a traditional P2P network simulation is not feasible. Instead, the application operates as a centralized authority managing a single, canonical blockchain state.

## Deployment on Vercel

Deploying this project is straightforward.

**1. Fork the Repository:**
   Start by forking this repository to your own GitHub account.

**2. Create a Vercel Project:**
   - Go to your Vercel dashboard and create a new project.
   - Import the repository you just forked.
   - Vercel will automatically detect the `vercel.json` file and configure the project as a Python application.

**3. Configure the Environment Variable:**
   - In the project settings on Vercel, navigate to the "Environment Variables" section.
   - Add a new environment variable with the following name and value:
     - **Name:** `MONGODB_URI`
     - **Value:** Your full MongoDB Atlas connection string (e.g., `mongodb+srv://...`).

**4. Deploy:**
   - Trigger a deployment. Vercel will install the dependencies from `requirements.txt` and deploy the application.
   - Once deployed, your API will be live!

## API Endpoints

The API is fully documented using Swagger UI. Once you have deployed the application, you can access the interactive documentation by navigating to the `/docs` path on your deployment URL.

Here is a summary of the available endpoints:

### Wallet
- `POST /api/v1/wallet/create`: Creates a new wallet (key pair and address).
- `GET /api/v1/wallet/balance/{address}`: Checks the balance of an address.
- `GET /api/v1/wallet/transactions/{address}`: Retrieves the transaction history for an address.

### Core Blockchain
- `POST /api/v1/transactions/create`: Creates a new, signed transaction and adds it to the mempool.
- `POST /api/v1/mine`: Mines a new block, including transactions from the mempool.

### Blockchain Explorer
- `GET /api/v1/explorer/block/height/{height}`: Retrieves a block by its height.
- `GET /api/v1/explorer/transaction/{tx_id}`: Retrieves a transaction by its ID.

### Exchange
- `POST /api/v1/exchange/deposit`: Deposits virtual currency for a user.
- `GET /api/v1/exchange/balances/{user_id}`: Gets a user's balances on the exchange.
- `POST /api/v1/exchange/order`: Places a new bid or ask order.
- `GET /api/v1/exchange/orderbook/{pair}`: Retrieves the order book for a given trading pair.
