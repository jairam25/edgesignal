import sqlite3
import time
import requests
from datetime import datetime
from core.database import get_connection
from config.assets import CRYPTO_PAIRS


# Map our pair format to CoinGecko IDs
COINGECKO_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "POL": "polygon-ecosystem-token",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "APT": "aptos",
}

COINGECKO_URL = "https://api.coingecko.com/api/v3"


def fetch_crypto():
    """Fetch all crypto prices from CoinGecko."""
    print(f"\n[CRYPTO] Fetching {len(CRYPTO_PAIRS)} pairs...")

    # Extract coin symbols from pairs like "BTC/USDT" -> "BTC"
    symbols = [pair.split("/")[0] for pair in CRYPTO_PAIRS]

    # Build CoinGecko IDs list
    ids = []
    for sym in symbols:
        if sym in COINGECKO_MAP:
            ids.append(COINGECKO_MAP[sym])
        else:
            print(f"  [SKIP] No CoinGecko mapping for {sym}")

    if not ids:
        print("[CRYPTO] No valid IDs to fetch.")
        return []

    # CoinGecko allows batch query
    ids_str = ",".join(ids)

    try:
        response = requests.get(
            f"{COINGECKO_URL}/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ids_str,
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "sparkline": False,
                "price_change_percentage": "24h",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

    except Exception as e:
        print(f"[ERROR] CoinGecko API failed: {e}")
        return []

    # Reverse map: coingecko_id -> symbol
    id_to_symbol = {v: k for k, v in COINGECKO_MAP.items()}

    results = []
    for coin in data:
        symbol = id_to_symbol.get(coin["id"])
        if not symbol:
            continue

        pair = f"{symbol}/USDT"

        results.append({
            "pair": pair,
            "price": coin.get("current_price", 0),
            "high_24h": coin.get("high_24h", 0),
            "low_24h": coin.get("low_24h", 0),
            "volume_24h": coin.get("total_volume", 0),
        "change_pct_24h": round(coin.get("price_change_percentage_24h") or 0, 4),
            "market_cap": coin.get("market_cap", 0),
        })

        price_display = coin.get('current_price') or 0
        change_display = coin.get('price_change_percentage_24h') or 0
        print(f"  {pair}: ${price_display:,.2f}  ({change_display:+.2f}%)")

    if results:
        save_crypto(results)

    print(f"[CRYPTO] Done — {len(results)} pairs fetched.")
    return results


def save_crypto(records, max_retries=3):
    """Save crypto prices to database with retry on lock."""
    if not records:
        return

    rows = [(
        r["pair"], r["price"], r["high_24h"], r["low_24h"],
        r["volume_24h"], r["change_pct_24h"], r["market_cap"]
    ) for r in records]

    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO crypto_prices
                (pair, price, high_24h, low_24h, volume_24h, change_pct_24h, market_cap)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            print(f"  [DB] Saved {len(records)} crypto records.")
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"  [DB] Locked, retrying ({attempt + 1}/{max_retries})...")
                time.sleep(0.5 * (attempt + 1))
            else:
                print(f"  [DB] Error saving crypto records: {e}")
                raise
        finally:
            if conn:
                conn.close()


if __name__ == "__main__":
    fetch_crypto()