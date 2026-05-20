import yfinance as yf
from datetime import datetime
from core.database import get_connection
from config.assets import COMMODITY_TICKERS


def fetch_commodities():
    """Fetch all commodity futures prices."""
    print(f"\n[COMMODITIES] Fetching {len(COMMODITY_TICKERS)} commodities...")

    tickers = list(COMMODITY_TICKERS.values())
    names = list(COMMODITY_TICKERS.keys())

    results = []

    try:
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            group_by="ticker",
            progress=False,
            threads=True,
        )

        for name, ticker in COMMODITY_TICKERS.items():
            try:
                if len(tickers) == 1:
                    df = data
                else:
                    df = data[ticker]

                if df.empty:
                    print(f"  [SKIP] {name} ({ticker}): no data")
                    continue

                latest = df.iloc[-1]
                first = df.iloc[0]

                price = round(float(latest["Close"]), 4)
                open_price = round(float(first["Open"]), 4)
                volume = int(df["Volume"].sum())
                change_pct = round(((price - open_price) / open_price) * 100, 4) if open_price else 0

                results.append({
                    "name": name,
                    "ticker": ticker,
                    "price": price,
                    "change_pct": change_pct,
                    "volume": volume,
                })

                # Display formatting based on price range
                if price > 100:
                    print(f"  {name}: ${price:,.2f}  ({change_pct:+.2f}%)")
                else:
                    print(f"  {name}: ${price:.4f}  ({change_pct:+.2f}%)")

            except Exception as e:
                print(f"  [SKIP] {name} ({ticker}): {e}")

    except Exception as e:
        print(f"[ERROR] Commodity download failed: {e}")

    if results:
        save_commodities(results)

    print(f"[COMMODITIES] Done — {len(results)} commodities fetched.")
    return results


def save_commodities(records):
    """Save commodity prices to database."""
    conn = get_connection()
    cursor = conn.cursor()

    for r in records:
        cursor.execute("""
            INSERT INTO commodity_prices
            (name, ticker, price, change_pct, volume)
            VALUES (?, ?, ?, ?, ?)
        """, (
            r["name"], r["ticker"], r["price"],
            r["change_pct"], r["volume"]
        ))

    conn.commit()
    conn.close()
    print(f"  [DB] Saved {len(records)} commodity records.")


if __name__ == "__main__":
    fetch_commodities()