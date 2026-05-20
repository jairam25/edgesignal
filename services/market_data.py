import sqlite3
import time
import yfinance as yf
from datetime import datetime
from core.database import get_connection
from config.assets import (
    ALL_STOCK_TICKERS, ETF_TICKERS, INDEX_TICKERS
)
from config.settings import settings


def fetch_batch(tickers, asset_type):
    """Fetch live price data for a batch of tickers."""
    results = []
    try:
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            group_by="ticker",
            progress=False,
            threads=True
        )

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    df = data
                else:
                    df = data[ticker]

                if df.empty:
                    continue

                latest = df.iloc[-1]
                first = df.iloc[0]

                price = round(float(latest["Close"]), 4)
                open_price = round(float(first["Open"]), 4)
                high = round(float(df["High"].max()), 4)
                low = round(float(df["Low"].min()), 4)
                volume = int(df["Volume"].sum())
                change_pct = round(((price - open_price) / open_price) * 100, 4) if open_price else 0

                results.append({
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "price": price,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "change_pct": change_pct,
                })

            except Exception as e:
                print(f"  [SKIP] {ticker}: {e}")

    except Exception as e:
        print(f"[ERROR] Batch download failed: {e}")

    return results


def save_prices(records, max_retries=3):
    """Save fetched prices to database with retry on lock."""
    if not records:
        return

    rows = [(
        r["ticker"], r["asset_type"], r["price"], r["open"],
        r["high"], r["low"], r["volume"], r["change_pct"]
    ) for r in records]

    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO market_prices
                (ticker, asset_type, price, open, high, low, volume, change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            print(f"  [DB] Saved {len(records)} records.")
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"  [DB] Locked, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(0.5 * (attempt + 1))
            else:
                print(f"  [DB] Error saving records: {e}")
                raise
        finally:
            if conn:
                conn.close()


def fetch_stocks():
    """Fetch all stock prices."""
    print(f"\n[STOCKS] Fetching {len(ALL_STOCK_TICKERS)} tickers...")
    # yfinance handles batches well, but chunk to avoid timeouts
    chunk_size = 15
    all_results = []

    for i in range(0, len(ALL_STOCK_TICKERS), chunk_size):
        chunk = ALL_STOCK_TICKERS[i:i + chunk_size]
        print(f"  Batch {i // chunk_size + 1}: {', '.join(chunk[:5])}...")
        results = fetch_batch(chunk, "stock")
        all_results.extend(results)
        time.sleep(1)  # respect rate limits

    if all_results:
        save_prices(all_results)
    print(f"[STOCKS] Done — {len(all_results)} tickers fetched.")
    return all_results


def fetch_etfs():
    """Fetch all ETF prices."""
    print(f"\n[ETFs] Fetching {len(ETF_TICKERS)} tickers...")
    results = fetch_batch(ETF_TICKERS, "etf")
    if results:
        save_prices(results)
    print(f"[ETFs] Done — {len(results)} tickers fetched.")
    return results


def fetch_indices():
    """Fetch all index prices."""
    tickers = list(INDEX_TICKERS.values())
    names = list(INDEX_TICKERS.keys())
    print(f"\n[INDICES] Fetching {len(tickers)}: {', '.join(names)}...")
    results = fetch_batch(tickers, "index")
    if results:
        save_prices(results)
    print(f"[INDICES] Done — {len(results)} fetched.")
    return results


def fetch_all_market_data():
    """Master function — fetches everything."""
    print("=" * 50)
    print(f"[MARKET DATA] Starting full fetch — {datetime.now()}")
    print("=" * 50)

    stocks = fetch_stocks()
    etfs = fetch_etfs()
    indices = fetch_indices()

    total = len(stocks) + len(etfs) + len(indices)
    print(f"\n[MARKET DATA] Complete — {total} total records saved.")
    return {"stocks": stocks, "etfs": etfs, "indices": indices}


if __name__ == "__main__":
    fetch_all_market_data()