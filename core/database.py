import sqlite3
import os
from datetime import datetime
from config.settings import settings


def get_connection():
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""

    -- Live & historical price data for stocks, ETFs, indices
    CREATE TABLE IF NOT EXISTS market_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        asset_type TEXT NOT NULL,  -- 'stock', 'etf', 'index'
        price REAL,
        open REAL,
        high REAL,
        low REAL,
        volume INTEGER,
        change_pct REAL,
        market_cap REAL,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Crypto prices
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT NOT NULL,
        price REAL,
        high_24h REAL,
        low_24h REAL,
        volume_24h REAL,
        change_pct_24h REAL,
        market_cap REAL,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Commodity futures
    CREATE TABLE IF NOT EXISTS commodity_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ticker TEXT NOT NULL,
        price REAL,
        change_pct REAL,
        volume INTEGER,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Polymarket prediction contracts
    CREATE TABLE IF NOT EXISTS polymarket_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        condition_id TEXT NOT NULL,
        question TEXT,
        market_price REAL,
        ai_probability REAL,
        edge REAL,
        volume REAL,
        liquidity REAL,
        end_date TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- FRED macro economic data
    CREATE TABLE IF NOT EXISTS macro_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_name TEXT NOT NULL,
        series_id TEXT NOT NULL,
        value REAL,
        date TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- AI-generated signals (the core output)
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        signal_type TEXT NOT NULL,  -- 'BUY', 'SELL', 'ALERT', 'EDGE'
        confidence INTEGER NOT NULL,
        headline TEXT,
        analysis TEXT,
        data_snapshot TEXT,  -- JSON blob of data that triggered it
        sent_to_telegram INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Portfolio tracking (for P&L, green/red)
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        entry_price REAL NOT NULL,
        current_price REAL,
        quantity REAL NOT NULL,
        side TEXT DEFAULT 'LONG',  -- 'LONG' or 'SHORT'
        pnl REAL DEFAULT 0,
        pnl_pct REAL DEFAULT 0,
        status TEXT DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED'
        opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP
    );

    -- Sentiment scores from Reddit/news
    CREATE TABLE IF NOT EXISTS sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        source TEXT NOT NULL,  -- 'reddit', 'news', 'twitter'
        score REAL,
        post_count INTEGER,
        summary TEXT,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for fast queries
    CREATE INDEX IF NOT EXISTS idx_market_ticker ON market_prices(ticker, fetched_at);
    CREATE INDEX IF NOT EXISTS idx_crypto_pair ON crypto_prices(pair, fetched_at);
    CREATE INDEX IF NOT EXISTS idx_commodity_ticker ON commodity_prices(ticker, fetched_at);
    CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
    CREATE INDEX IF NOT EXISTS idx_signals_asset ON signals(asset_type, ticker);
    CREATE INDEX IF NOT EXISTS idx_portfolio_status ON portfolio(status);
    CREATE INDEX IF NOT EXISTS idx_polymarket_edge ON polymarket_contracts(edge);

    """)

    conn.commit()
    conn.close()
    print("[DB] EdgeSignal database initialized successfully.")


if __name__ == "__main__":
    init_db()