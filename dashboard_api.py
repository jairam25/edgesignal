"""
EdgeSignal Dashboard API with WebSocket streaming
Run: uvicorn dashboard_api:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import asyncio
from pathlib import Path
from datetime import datetime

app = FastAPI(title="EdgeSignal API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).resolve().parent / "data" / "edgesignal.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Connected WebSocket clients ───────────────────
connected_clients = set()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[WS] Client connected. Total: {len(connected_clients)}")

    try:
        while True:
            # Send latest data every 30 seconds
            data = get_all_live_data()
            await websocket.send_json(data)
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(connected_clients)}")
    except Exception:
        connected_clients.discard(websocket)


def get_all_live_data():
    """Get all live data for WebSocket broadcast."""
    conn = get_db()

    data = {
        "timestamp": datetime.now().isoformat(),
        "stocks": [],
        "crypto": [],
        "commodities": [],
        "signals": [],
        "portfolio": [],
        "overview": {},
    }

    try:
        # Stocks
        rows = conn.execute("""
            SELECT ticker, asset_type, price, open, high, low, volume, change_pct
            FROM market_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices)
            ORDER BY ABS(change_pct) DESC
        """).fetchall()
        data["stocks"] = [dict(r) for r in rows]

        # Crypto
        rows = conn.execute("""
            SELECT pair, price, high_24h, low_24h, volume_24h, change_pct_24h, market_cap
            FROM crypto_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM crypto_prices)
            ORDER BY market_cap DESC
        """).fetchall()
        data["crypto"] = [dict(r) for r in rows]

        # Commodities
        rows = conn.execute("""
            SELECT name, ticker, price, change_pct, volume
            FROM commodity_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM commodity_prices)
        """).fetchall()
        data["commodities"] = [dict(r) for r in rows]

        # Latest signals
        rows = conn.execute("""
            SELECT id, asset_type, ticker, signal_type, confidence, headline, analysis, created_at
            FROM signals ORDER BY created_at DESC LIMIT 20
        """).fetchall()
        data["signals"] = [dict(r) for r in rows]

        # Portfolio
        rows = conn.execute("""
            SELECT id, ticker, asset_type, entry_price, current_price, quantity, side, pnl, pnl_pct, status
            FROM portfolio WHERE status = 'OPEN' ORDER BY pnl DESC
        """).fetchall()
        data["portfolio"] = [dict(r) for r in rows]

        # Overview
        signals_today = conn.execute(
            "SELECT COUNT(*) as c FROM signals WHERE DATE(created_at) = DATE('now')"
        ).fetchone()["c"]

        total_pnl = conn.execute(
            "SELECT SUM(pnl) as total FROM portfolio WHERE status = 'OPEN'"
        ).fetchone()["total"] or 0

        top_gainers = conn.execute("""
            SELECT ticker, price, change_pct FROM market_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
            ORDER BY change_pct DESC LIMIT 5
        """).fetchall()

        top_losers = conn.execute("""
            SELECT ticker, price, change_pct FROM market_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
            ORDER BY change_pct ASC LIMIT 5
        """).fetchall()

        data["overview"] = {
            "signals_today": signals_today,
            "total_pnl": total_pnl,
            "open_positions": len(data["portfolio"]),
            "top_gainers": [dict(r) for r in top_gainers],
            "top_losers": [dict(r) for r in top_losers],
        }

    except Exception as e:
        print(f"[WS] Data error: {e}")

    conn.close()
    return data


# ─── REST Endpoints (keep existing) ───────────────

@app.get("/api/stocks")
def get_stocks():
    conn = get_db()
    rows = conn.execute("""
        SELECT ticker, asset_type, price, open, high, low, volume, change_pct, fetched_at
        FROM market_prices WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices)
        ORDER BY ABS(change_pct) DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/crypto")
def get_crypto():
    conn = get_db()
    rows = conn.execute("""
        SELECT pair, price, high_24h, low_24h, volume_24h, change_pct_24h, market_cap, fetched_at
        FROM crypto_prices WHERE fetched_at = (SELECT MAX(fetched_at) FROM crypto_prices)
        ORDER BY market_cap DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/commodities")
def get_commodities():
    conn = get_db()
    rows = conn.execute("""
        SELECT name, ticker, price, change_pct, volume, fetched_at
        FROM commodity_prices WHERE fetched_at = (SELECT MAX(fetched_at) FROM commodity_prices)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/macro")
def get_macro():
    conn = get_db()
    rows = conn.execute("""
        SELECT series_name, series_id, value, date, fetched_at
        FROM macro_data WHERE fetched_at = (SELECT MAX(fetched_at) FROM macro_data)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/polymarket")
def get_polymarket():
    conn = get_db()
    rows = conn.execute("""
        SELECT condition_id, question, market_price, ai_probability, edge, volume, liquidity, end_date, fetched_at
        FROM polymarket_contracts WHERE fetched_at = (SELECT MAX(fetched_at) FROM polymarket_contracts)
        ORDER BY volume DESC LIMIT 25
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/signals")
def get_signals():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, asset_type, ticker, signal_type, confidence, headline, analysis, created_at
        FROM signals ORDER BY created_at DESC LIMIT 30
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/sentiment")
def get_sentiment():
    conn = get_db()
    rows = conn.execute("""
        SELECT ticker, source, score, post_count, summary, fetched_at
        FROM sentiment WHERE fetched_at = (SELECT MAX(fetched_at) FROM sentiment)
        ORDER BY post_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/portfolio")
def get_portfolio():
    conn = get_db()
    rows = conn.execute("""
        SELECT id, ticker, asset_type, entry_price, current_price, quantity, side, pnl, pnl_pct, status, opened_at, closed_at
        FROM portfolio ORDER BY opened_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/overview")
def get_overview():
    conn = get_db()
    signals_today = conn.execute(
        "SELECT COUNT(*) as c FROM signals WHERE DATE(created_at) = DATE('now')"
    ).fetchone()["c"]
    portfolio = conn.execute("""
        SELECT COUNT(*) as total_positions,
            SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) as open_positions,
            SUM(CASE WHEN status='OPEN' THEN pnl ELSE 0 END) as total_pnl,
            SUM(CASE WHEN status='OPEN' AND pnl >= 0 THEN 1 ELSE 0 END) as winning,
            SUM(CASE WHEN status='OPEN' AND pnl < 0 THEN 1 ELSE 0 END) as losing
        FROM portfolio
    """).fetchone()
    latest_stock = conn.execute("SELECT MAX(fetched_at) as t FROM market_prices").fetchone()["t"]
    latest_crypto = conn.execute("SELECT MAX(fetched_at) as t FROM crypto_prices").fetchone()["t"]
    top_gainers = conn.execute("""
        SELECT ticker, price, change_pct FROM market_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
        ORDER BY change_pct DESC LIMIT 5
    """).fetchall()
    top_losers = conn.execute("""
        SELECT ticker, price, change_pct FROM market_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
        ORDER BY change_pct ASC LIMIT 5
    """).fetchall()
    conn.close()
    return {
        "signals_today": signals_today,
        "portfolio": dict(portfolio),
        "latest_stock_update": latest_stock,
        "latest_crypto_update": latest_crypto,
        "top_gainers": [dict(r) for r in top_gainers],
        "top_losers": [dict(r) for r in top_losers],
    }


@app.get("/api/performance")
def get_performance():
    conn = get_db()
    try:
        trades = conn.execute("""
            SELECT ticker, signal_type, entry_price, exit_price, pnl, pnl_pct, exit_reason, closed_at
            FROM signal_performance ORDER BY closed_at DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in trades]
    except Exception:
        conn.close()
        return []


@app.get("/api/mtf/{ticker}")
def get_mtf(ticker: str):
    """Get multi-timeframe analysis for a specific ticker."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT ticker, overall_bias, strength, timeframe_data, created_at
            FROM mtf_analysis WHERE ticker = ?
            ORDER BY created_at DESC LIMIT 1
        """, (ticker.upper(),)).fetchone()
        conn.close()
        if row:
            result = dict(row)
            result["timeframe_data"] = json.loads(result["timeframe_data"]) if result["timeframe_data"] else {}
            return result
        return {"error": "No MTF data for this ticker"}
    except Exception:
        conn.close()
        return {"error": "MTF table not available yet"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)