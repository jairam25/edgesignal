import requests
import time
from datetime import datetime
from core.database import get_connection
from config.settings import settings


GAMMA_URL = "https://gamma-api.polymarket.com"


def fetch_polymarket():
    """Fetch active Polymarket prediction contracts via Gamma API."""
    print(f"\n[POLYMARKET] Fetching active markets...")

    results = []

    try:
        response = requests.get(
            f"{GAMMA_URL}/markets",
            params={
                "closed": False,
                "active": True,
                "limit": 100,
                "order": "volume",
                "ascending": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        markets = response.json()

        if not markets:
            print("  [WARN] No markets returned.")
            return []

        for market in markets:
            try:
                question = market.get("question", "")
                condition_id = market.get("conditionId", market.get("id", ""))

                # Gamma API uses outcomePrices as a JSON string like "[0.62, 0.38]"
                outcome_prices = market.get("outcomePrices", "")
                price = None
                if outcome_prices:
                    try:
                        import json
                        prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
                        if prices and len(prices) > 0:
                            price = float(prices[0])
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass

                if price is None:
                    price = float(market.get("bestAsk") or market.get("lastTradePrice") or 0) or None

                volume = float(market.get("volume", 0) or 0)
                liquidity = float(market.get("liquidity", 0) or 0)
                end_date = market.get("endDate", market.get("end_date_iso", ""))

                if not question or not condition_id:
                    continue

                # Skip markets with zero volume — they're dead
                if volume < 1000:
                    continue

                results.append({
                    "condition_id": str(condition_id),
                    "question": question,
                    "market_price": price,
                    "volume": volume,
                    "liquidity": liquidity,
                    "end_date": end_date,
                })

            except Exception as e:
                print(f"  [SKIP] Market parse error: {e}")
                continue

        # Sort by volume and print top 15
        results.sort(key=lambda x: x["volume"], reverse=True)

        for r in results[:15]:
            prob = f"{r['market_price']*100:.0f}%" if r["market_price"] else "N/A"
            vol = f"${r['volume']:,.0f}"
            q = r["question"][:80]
            print(f"  [{prob}] {q}  (Vol: {vol})")

    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot reach Polymarket API. Try with VPN if geo-blocked.")
        return []
    except Exception as e:
        print(f"[ERROR] Polymarket fetch failed: {e}")
        return []

    if results:
        save_polymarket(results)

    print(f"[POLYMARKET] Done — {len(results)} active markets fetched.")
    return results


def save_polymarket(records):
    """Save Polymarket data to database."""
    conn = get_connection()
    cursor = conn.cursor()

    for r in records:
        cursor.execute("""
            INSERT INTO polymarket_contracts
            (condition_id, question, market_price, volume, liquidity, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            r["condition_id"], r["question"], r["market_price"],
            r["volume"], r["liquidity"], r["end_date"]
        ))

    conn.commit()
    conn.close()
    print(f"  [DB] Saved {len(records)} Polymarket contracts.")


if __name__ == "__main__":
    fetch_polymarket()