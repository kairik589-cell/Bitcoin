# Simulasi API Bitcoin (Bitcoin Simulation API)

Selamat datang di Simulasi API Bitcoin! Proyek ini adalah implementasi *backend* yang komprehensif dari sebuah sistem *cryptocurrency* yang terinspirasi oleh Bitcoin, dibangun menggunakan Python dan FastAPI. Proyek ini dirancang sebagai alat pembelajaran untuk memahami konsep-konsep inti di balik teknologi blockchain, sambil disesuaikan untuk dapat di-deploy dengan mudah di platform *serverless* seperti Vercel.

**URL Aplikasi yang sudah di-deploy:** [https://bitcoin-navy-delta.vercel.app/docs](https://bitcoin-navy-delta.vercel.app/docs)

---

## 🏛️ Arsitektur & Desain

Sistem Bitcoin asli bersifat terdesentralisasi. Meskipun menjalankan jaringan *peer-to-peer* (P2P) yang sesungguhnya sulit di lingkungan *serverless* seperti Vercel, proyek ini mengambil langkah lebih jauh dari sekadar model terpusat sederhana.

Arsitektur kami adalah **Simulasi Jaringan P2P Terdesentralisasi di Atas Server Tunggal**:
- **Beberapa Node Virtual:** Aplikasi ini membuat beberapa objek `Node` dalam memori saat startup. Setiap `Node` memiliki instance `Blockchain`-nya sendiri, lengkap dengan rantai blok, set UTXO, dan mempool yang terpisah.
- **Mekanisme Penyiaran (Broadcast):** Ketika API menerima transaksi atau blok baru, ia tidak memprosesnya secara langsung. Sebaliknya, ia "menyiarkannya" ke semua `Node` virtual di dalam `Network`.
- **Konsensus Node Individual:** Setiap `Node` secara independen memvalidasi transaksi dan blok yang diterimanya. Saat menambang, sebuah *node* (dipilih secara acak) akan membangun blok di atas versi rantainya sendiri.
- **API sebagai Gateway:** Endpoint API bertindak sebagai "gateway" ke jaringan yang disimulasikan ini. Endpoint *read-only* akan mengambil data dari *node* acak (mensimulasikan koneksi ke satu titik di jaringan), sementara endpoint *write* akan berinteraksi dengan seluruh jaringan.

Pendekatan ini memungkinkan kita untuk mensimulasikan dan mempelajari konsep-konsep desentralisasi yang kompleks—seperti penyiaran di jaringan, perbedaan *state* antar *node* (misalnya, mempool yang berbeda), dan persaingan antar penambang—dalam lingkungan tunggal yang dapat di-deploy.

---

## 🚀 Panduan Setup Lokal

Untuk menjalankan API ini di mesin lokal Anda, ikuti langkah-langkah berikut:

1.  **Clone Repositori:**
    ```bash
    git clone <URL_REPOSITORI_ANDA>
    cd <NAMA_DIREKTORI>
    ```

2.  **Install Dependensi:**
    Pastikan Anda memiliki Python 3.8+ terinstal. Kemudian, jalankan:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Jalankan Server:**
    Gunakan `uvicorn` untuk memulai server API:
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
    Flag `--reload` akan secara otomatis me-restart server setiap kali ada perubahan kode.

4.  **Akses Dokumentasi Interaktif:**
    Buka browser Anda dan navigasikan ke [http://localhost:8000/docs](http://localhost:8000/docs). Anda akan melihat dokumentasi API interaktif yang dihasilkan oleh Swagger UI, di mana Anda bisa menguji setiap endpoint secara langsung.

---

## 📖 Dokumentasi API Lengkap

Berikut adalah daftar semua endpoint yang tersedia.

### Wallet

#### `POST /wallet/create`
Membuat pasangan kunci kriptografi (dompet) baru.
- **Request Body:** Tidak ada.
- **Contoh Response:**
  ```json
  {
    "private_key": "...",
    "public_key": "...",
    "address": "addr_..."
  }
  ```

### Transaksi

#### `POST /transactions/create`
Membuat, menandatangani, dan menyiarkan transaksi baru ke mempool.
- **Request Body:**
  ```json
  {
    "sender_private_key": "...",
    "recipient_address": "addr_...",
    "amount": 10.5,
    "fee": 0.1
  }
  ```
- **Contoh Response:** Objek transaksi yang berhasil dibuat.

### Blockchain & Penambangan

#### `POST /mine`
Memulai proses penambangan blok baru. Ini akan mengambil semua transaksi dari mempool, membuat blok, dan menambahkannya ke rantai.
- **Request Body:**
  ```json
  {
    "miner_address": "addr_..."
  }
  ```
- **Contoh Response:** Objek blok baru yang berhasil ditambang.

### API Explorer (Read-Only)

#### `GET /stats`
Mendapatkan statistik umum tentang blockchain.

#### `GET /chain/is-valid`
Memverifikasi integritas seluruh blockchain.

#### `GET /mempool`
Melihat semua transaksi yang saat ini menunggu di mempool.

#### `GET /block/{block_hash}`
Mengambil detail lengkap dari sebuah blok berdasarkan hash-nya.

#### `GET /transaction/{tx_id}`
Mengambil detail lengkap dari sebuah transaksi berdasarkan ID-nya.

#### `GET /address/{address}/utxos`
Mendapatkan semua UTXO (Unspent Transaction Outputs) yang dimiliki oleh sebuah alamat. Endpoint ini sangat penting bagi sebuah dompet untuk mengetahui dana mana yang bisa dibelanjakan.

### API v1 (Dompet & Bursa)

Endpoint-endpoint ini menyediakan abstraksi tingkat tinggi di atas API inti.

#### `GET /api/v1/wallet/{address}/balance`
Menghitung dan mengembalikan total saldo sebuah alamat.

#### `GET /api/v1/wallet/{address}/history`
Menyediakan riwayat transaksi yang disederhanakan untuk sebuah alamat.

#### `GET /api/v1/exchange/orderbook`
Mengambil *order book* saat ini, menampilkan semua order jual dan beli.

#### `POST /api/v1/exchange/order`
Menempatkan order jual (`ask`) atau beli (`bid`) baru ke dalam *order book*.

---

## 💡 Konsep Inti yang Diimplementasikan

- **Model UTXO (Unspent Transaction Output):** Transaksi tidak mengubah saldo, melainkan mengkonsumsi output dari transaksi sebelumnya dan membuat output baru.
- **Kriptografi Kunci Publik (ECDSA):** Menggunakan kurva `SECP256K1` (sama seperti Bitcoin) untuk membuat pasangan kunci dan menandatangani transaksi.
- **Scripting (Pay-to-Public-Key-Hash - P2PKH):** Mensimulasikan mekanisme penguncian dan pembukaan dana yang paling umum di Bitcoin.
- **Proof-of-Work (PoW):** Penambang harus memecahkan teka-teki komputasi (mencari *nonce*) untuk bisa menambahkan blok baru.
- **Merkle Trees:** Setiap blok menyertakan *merkle root* dari semua transaksinya, memastikan bahwa riwayat transaksi tidak dapat diubah tanpa mengubah hash blok.
