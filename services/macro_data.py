import requests
import time
from datetime import datetime
from core.database import get_connection
from config.assets import FRED_SERIES
from config.settings import settings


FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_macro():
    """Fetch latest values for all FRED economic series."""
    print(f"\n[MACRO] Fetching {len(FRED_SERIES)} economic indicators...")

    if not settings.FRED_API_KEY:
        print("[ERROR] FRED_API_KEY not set in .env — skipping macro data.")
        return []

    results = []

    for name, series_id in FRED_SERIES.items():
        try:
            response = requests.get(
                FRED_URL,
                params={
                    "series_id": series_id,
                    "api_key": settings.FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            observations = data.get("observations", [])
            if not observations:
                print(f"  [SKIP] {name}: no data returned")
                continue

            latest = observations[0]
            value = latest.get("value", ".")

            # FRED uses "." for missing values
            if value == ".":
                print(f"  [SKIP] {name}: value pending")
                continue

            value = float(value)
            date = latest.get("date", "")

            results.append({
                "series_name": name,
                "series_id": series_id,
                "value": value,
                "date": date,
            })

            print(f"  {name}: {value:,.2f}  (as of {date})")

            time.sleep(0.5)  # respect FRED rate limits

        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    if results:
        save_macro(results)

    print(f"[MACRO] Done — {len(results)} indicators fetched.")
    return results


def save_macro(records):
    """Save macro data to database."""
    conn = get_connection()
    cursor = conn.cursor()

    for r in records:
        cursor.execute("""
            INSERT INTO macro_data
            (series_name, series_id, value, date)
            VALUES (?, ?, ?, ?)
        """, (
            r["series_name"], r["series_id"],
            r["value"], r["date"]
        ))

    conn.commit()
    conn.close()
    print(f"  [DB] Saved {len(records)} macro records.")


if __name__ == "__main__":
    fetch_macro()