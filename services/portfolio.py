"""
Portfolio management — position tracking and P&L summary.

Provides:
  - get_portfolio_summary()     → dict for email/dashboard use
  - get_latest_price()          → latest price from DB
  - create_position_from_signal() → auto-open position from AI signal
  - update_all_positions()      → refresh current prices & P&L
  - close_position()            → close an open position
  - auto_close_stale_positions() → close positions older than N days
  - send_portfolio_update()     → push update to Telegram
"""

import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Lazy DB connection helper
# (When core.database is available it provides get_connection; otherwise
#  we return None and all functions degrade gracefully.)
# ---------------------------------------------------------------------------
_db_available = False
_get_connection = None

try:
    from core.database import get_connection as _get_connection_impl

    _get_connection = _get_connection_impl
    _db_available = True
except ImportError:
    import sqlite3
    import os

    _DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "edgesignal.db")

    def _get_connection():
        """Fallback SQLite connection when core.database is unavailable."""
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    _db_available = True  # fallback path works


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------
def get_portfolio_summary():
    """Return a summary dict suitable for email briefings.

    Returns:
        dict with keys:
          - open_positions:   list of dicts
          - closed_today:     list of dicts
          - total_open_pnl:   float
          - total_closed_pnl: float
          - winners:          int
          - losers:           int
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        open_positions = cursor.execute(
            """
            SELECT ticker, side, entry_price, current_price, pnl, pnl_pct
            FROM portfolio WHERE status = 'OPEN'
            ORDER BY pnl DESC
            """
        ).fetchall()

        closed_today = cursor.execute(
            """
            SELECT ticker, side, pnl, pnl_pct
            FROM portfolio
            WHERE status = 'CLOSED' AND DATE(closed_at) = DATE('now')
            """
        ).fetchall()

        total_open_pnl = sum(p["pnl"] or 0 for p in open_positions)
        total_closed_pnl = sum(p["pnl"] or 0 for p in closed_today)
        winners = len([p for p in open_positions if (p["pnl"] or 0) > 0])
        losers = len([p for p in open_positions if (p["pnl"] or 0) < 0])

        conn.close()

        return {
            "open_positions": [dict(p) for p in open_positions],
            "closed_today": [dict(p) for p in closed_today],
            "total_open_pnl": total_open_pnl,
            "total_closed_pnl": total_closed_pnl,
            "winners": winners,
            "losers": losers,
        }
    except Exception as e:
        print(f"[PORTFOLIO] get_portfolio_summary error: {e}")
        return {
            "open_positions": [],
            "closed_today": [],
            "total_open_pnl": 0.0,
            "total_closed_pnl": 0.0,
            "winners": 0,
            "losers": 0,
        }


# ---------------------------------------------------------------------------
# Price lookup
# ---------------------------------------------------------------------------
def get_latest_price(ticker, asset_type="stock"):
    """Get the latest price for a ticker from the database."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        price = None

        # Stocks
        row = cursor.execute(
            "SELECT price FROM market_prices WHERE ticker = ? ORDER BY fetched_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        if row and row["price"]:
            price = row["price"]

        # Crypto
        if not price:
            pair = f"{ticker}/USDT"
            row = cursor.execute(
                "SELECT price FROM crypto_prices WHERE pair = ? ORDER BY fetched_at DESC LIMIT 1",
                (pair,),
            ).fetchone()
            if row and row["price"]:
                price = row["price"]

        # Commodities
        if not price:
            row = cursor.execute(
                "SELECT price FROM commodity_prices WHERE ticker = ? OR name = ? ORDER BY fetched_at DESC LIMIT 1",
                (ticker, ticker),
            ).fetchone()
            if row and row["price"]:
                price = row["price"]

        conn.close()
        return price
    except Exception as e:
        print(f"[PORTFOLIO] get_latest_price error: {e}")
        return None


# ---------------------------------------------------------------------------
# Position management
# ---------------------------------------------------------------------------
def create_position_from_signal(signal):
    """Auto-create a portfolio position from an AI signal."""
    from config.settings import settings

    conn = _get_connection()
    cursor = conn.cursor()

    ticker = signal.get("ticker", "")
    signal_type = signal.get("signal_type", "")
    asset_type = signal.get("asset_type", "")
    confidence = signal.get("confidence", 0)
    entry_price = signal.get("entry_price", 0)

    # Only create positions for BUY/SELL signals above threshold
    if signal_type not in ("BUY", "SELL"):
        return None
    threshold = int(getattr(settings, "SIGNAL_CONFIDENCE_THRESHOLD", "70"))
    if confidence < threshold:
        return None

    # If no entry price from AI, get latest price
    if not entry_price:
        entry_price = get_latest_price(ticker, asset_type)
        if not entry_price:
            print(f"  [PORTFOLIO] No price found for {ticker} — skipping position")
            return None

    # Check for existing open position
    existing = cursor.execute(
        "SELECT id FROM portfolio WHERE ticker = ? AND status = 'OPEN'", (ticker,)
    ).fetchone()
    if existing:
        print(f"  [PORTFOLIO] Already have open position for {ticker} — skipping")
        conn.close()
        return None

    side = "LONG" if signal_type == "BUY" else "SHORT"
    default_capital = 1000
    quantity = round(default_capital / entry_price, 6) if entry_price > 0 else 0

    cursor.execute(
        """
        INSERT INTO portfolio
        (ticker, asset_type, entry_price, current_price, quantity, side, pnl, pnl_pct, status)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'OPEN')
        """,
        (ticker, asset_type, entry_price, entry_price, quantity, side),
    )

    position_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"  [PORTFOLIO] ✅ Opened {side} {ticker} @ ${entry_price:.2f} x {quantity:.4f}")
    return position_id


def update_all_positions():
    """Update current prices and P&L for all open positions."""
    conn = _get_connection()
    cursor = conn.cursor()

    positions = cursor.execute(
        "SELECT id, ticker, asset_type, entry_price, quantity, side FROM portfolio WHERE status = 'OPEN'"
    ).fetchall()

    if not positions:
        print("[PORTFOLIO] No open positions to update.")
        conn.close()
        return

    print(f"\n[PORTFOLIO] Updating {len(positions)} open positions...")

    updated = 0
    total_pnl = 0

    for pos in positions:
        current_price = get_latest_price(pos["ticker"], pos["asset_type"])
        if not current_price:
            continue

        entry = pos["entry_price"]
        qty = pos["quantity"]
        side = pos["side"]

        if side == "LONG":
            pnl = (current_price - entry) * qty
            pnl_pct = ((current_price - entry) / entry) * 100 if entry else 0
        else:
            pnl = (entry - current_price) * qty
            pnl_pct = ((entry - current_price) / entry) * 100 if entry else 0

        pnl = round(pnl, 2)
        pnl_pct = round(pnl_pct, 4)

        cursor.execute(
            "UPDATE portfolio SET current_price = ?, pnl = ?, pnl_pct = ? WHERE id = ?",
            (current_price, pnl, pnl_pct, pos["id"]),
        )

        total_pnl += pnl
        updated += 1

    conn.commit()
    conn.close()

    total_icon = "🟢" if total_pnl >= 0 else "🔴"
    print(f"\n  {total_icon} Total Portfolio P&L: ${total_pnl:+.2f}")
    print(f"[PORTFOLIO] Updated {updated} positions.")


def close_position(ticker, close_price=None):
    """Close an open position. Returns P&L or None."""
    conn = _get_connection()
    cursor = conn.cursor()

    pos = cursor.execute(
        "SELECT id, entry_price, quantity, side, asset_type FROM portfolio WHERE ticker = ? AND status = 'OPEN'",
        (ticker,),
    ).fetchone()

    if not pos:
        print(f"[PORTFOLIO] No open position for {ticker}")
        conn.close()
        return None

    if not close_price:
        close_price = get_latest_price(ticker, pos["asset_type"])
    if not close_price:
        print(f"[PORTFOLIO] Cannot get close price for {ticker}")
        conn.close()
        return None

    entry = pos["entry_price"]
    qty = pos["quantity"]
    side = pos["side"]

    if side == "LONG":
        pnl = (close_price - entry) * qty
        pnl_pct = ((close_price - entry) / entry) * 100
    else:
        pnl = (entry - close_price) * qty
        pnl_pct = ((entry - close_price) / entry) * 100

    pnl = round(pnl, 2)
    pnl_pct = round(pnl_pct, 4)

    cursor.execute(
        "UPDATE portfolio SET current_price = ?, pnl = ?, pnl_pct = ?, status = 'CLOSED', closed_at = ? WHERE id = ?",
        (close_price, pnl, pnl_pct, datetime.now().isoformat(), pos["id"]),
    )

    conn.commit()
    conn.close()

    icon = "🟢" if pnl >= 0 else "🔴"
    print(f"  {icon} [CLOSED] {ticker} ({side}): ${entry:.2f} → ${close_price:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)")
    return pnl


def auto_close_stale_positions(max_days=5):
    """Auto-close positions older than max_days."""
    conn = _get_connection()
    cursor = conn.cursor()

    stale = cursor.execute(
        "SELECT ticker FROM portfolio WHERE status = 'OPEN' AND opened_at < datetime('now', ?)",
        (f"-{max_days} days",),
    ).fetchall()

    conn.close()

    closed = 0
    for pos in stale:
        result = close_position(pos["ticker"])
        if result is not None:
            closed += 1

    if closed:
        print(f"[PORTFOLIO] Auto-closed {closed} stale positions (>{max_days} days old)")


# ---------------------------------------------------------------------------
# Telegram integration
# ---------------------------------------------------------------------------
def send_portfolio_update():
    """Send portfolio update to Telegram."""
    try:
        from bot.telegram_bot import send_message
    except ImportError:
        print("[PORTFOLIO] telegram_bot module not available.")
        return

    summary = get_portfolio_summary()
    positions = summary["open_positions"]

    if not positions:
        return

    total_pnl = summary["total_open_pnl"]
    pnl_icon = "🟢" if total_pnl >= 0 else "🔴"

    positions_text = ""
    for p in positions:
        icon = "🟢" if (p["pnl"] or 0) >= 0 else "🔴"
        positions_text += (
            f"\n  {icon} {p['ticker']} ({p['side']}): "
            f"${p['entry_price']:.2f} → ${p['current_price']:.2f} | "
            f"{p['pnl']:+.2f} ({p['pnl_pct']:+.2f}%)"
        )

    msg = f"""💼 <b>PORTFOLIO UPDATE</b>
━━━━━━━━━━━━━━━━━━━━

{pnl_icon} <b>Total P&L: ${total_pnl:+.2f}</b>
🏆 Winners: {summary['winners']} | 💀 Losers: {summary['losers']}

<b>Open Positions:</b>{positions_text}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
#EdgeSignal #Portfolio"""

    send_message(msg)
    print("[PORTFOLIO] Update sent to Telegram.")


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    summary = get_portfolio_summary()
    print(f"Open P&L: ${summary['total_open_pnl']:+.2f}")
    print(f"Winners: {summary['winners']}, Losers: {summary['losers']}")