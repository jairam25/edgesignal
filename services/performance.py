import json
from datetime import datetime
from core.database import get_connection
from config.settings import settings


def check_stop_loss_take_profit():
    """Auto-close positions that hit SL or TP levels."""
    conn = get_connection()
    cursor = conn.cursor()

    positions = cursor.execute("""
        SELECT p.id, p.ticker, p.asset_type, p.entry_price, p.current_price,
               p.quantity, p.side, p.pnl, p.pnl_pct,
               s.data_snapshot
        FROM portfolio p
        LEFT JOIN signals s ON s.ticker = p.ticker
            AND s.created_at = (
                SELECT MAX(created_at) FROM signals
                WHERE ticker = p.ticker
            )
        WHERE p.status = 'OPEN'
    """).fetchall()

    if not positions:
        return

    print(f"\n[PERFORMANCE] Checking SL/TP for {len(positions)} positions...")

    closed = 0
    for pos in positions:
        ticker = pos["ticker"]
        entry = pos["entry_price"]
        current = pos["current_price"]
        side = pos["side"]
        pnl_pct = pos["pnl_pct"] or 0

        if not current or not entry:
            continue

        # Default SL/TP if not set by AI signal
        # Stop Loss: -3% for stocks, -5% for crypto
        # Take Profit: +6% for stocks, +10% for crypto
        is_crypto = pos["asset_type"] in ("crypto",)
        default_sl = -5.0 if is_crypto else -3.0
        default_tp = 10.0 if is_crypto else 6.0

        # Try to get AI-defined SL/TP from signal
        sl_pct = default_sl
        tp_pct = default_tp

        if pos["data_snapshot"]:
            try:
                snapshot = json.loads(pos["data_snapshot"])
                # Look for stop_loss and take_profit in the signal
                for sig in snapshot.get("signals", []) if isinstance(snapshot, dict) else []:
                    if sig.get("ticker") == ticker:
                        if sig.get("stop_loss") and sig.get("entry_price"):
                            sl_pct = ((sig["stop_loss"] - sig["entry_price"]) / sig["entry_price"]) * 100
                        if sig.get("take_profit") and sig.get("entry_price"):
                            tp_pct = ((sig["take_profit"] - sig["entry_price"]) / sig["entry_price"]) * 100
            except (json.JSONDecodeError, TypeError):
                pass

        # Check if SL or TP hit
        hit = None
        if side == "LONG":
            if pnl_pct <= sl_pct:
                hit = "STOP_LOSS"
            elif pnl_pct >= tp_pct:
                hit = "TAKE_PROFIT"
        else:  # SHORT
            if pnl_pct <= sl_pct:
                hit = "STOP_LOSS"
            elif pnl_pct >= tp_pct:
                hit = "TAKE_PROFIT"

        if hit:
            # Close position
            pnl = pos["pnl"] or 0
            cursor.execute("""
                UPDATE portfolio
                SET status = 'CLOSED', closed_at = ?, pnl = ?, pnl_pct = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), pnl, pnl_pct, pos["id"]))

            # Record performance
            cursor.execute("""
                INSERT INTO signal_performance
                (ticker, signal_type, entry_price, exit_price, pnl, pnl_pct, exit_reason, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ticker, side, entry, current, pnl, pnl_pct, hit, datetime.now().isoformat()))

            icon = "🟢" if pnl >= 0 else "🔴"
            reason_icon = "🛑" if hit == "STOP_LOSS" else "🎯"
            print(f"  {icon} {reason_icon} {ticker} ({side}) — {hit} at ${current:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)")

            # Send Telegram alert
            send_sl_tp_alert(ticker, side, hit, entry, current, pnl, pnl_pct)

            closed += 1

    if closed:
        conn.commit()
        print(f"[PERFORMANCE] Auto-closed {closed} positions.")

    conn.close()


def send_sl_tp_alert(ticker, side, reason, entry, exit_price, pnl, pnl_pct):
    """Send SL/TP alert to Telegram."""
    try:
        from bot.telegram_bot import send_message

        icon = "🟢" if pnl >= 0 else "🔴"
        reason_icon = "🛑 STOP LOSS" if reason == "STOP_LOSS" else "🎯 TAKE PROFIT"

        msg = f"""{icon} <b>{reason_icon} HIT</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>{ticker}</b> ({side})
💰 Entry: ${entry:,.2f} → Exit: ${exit_price:,.2f}
📈 P&L: <b>${pnl:+.2f} ({pnl_pct:+.2f}%)</b>

Position auto-closed.
#EdgeSignal #{ticker} #AutoClose"""

        send_message(msg)
    except Exception as e:
        print(f"  [ERROR] SL/TP alert failed: {e}")


def calculate_performance_stats():
    """Calculate overall signal performance statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            signal_type TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            pnl_pct REAL,
            exit_reason TEXT,
            closed_at TIMESTAMP
        )
    """)
    conn.commit()

    # All closed trades
    trades = cursor.execute("""
        SELECT ticker, pnl, pnl_pct, exit_reason, closed_at
        FROM signal_performance
        ORDER BY closed_at DESC
    """).fetchall()

    if not trades:
        conn.close()
        return None

    total_trades = len(trades)
    winners = [t for t in trades if (t["pnl"] or 0) > 0]
    losers = [t for t in trades if (t["pnl"] or 0) < 0]
    breakeven = [t for t in trades if (t["pnl"] or 0) == 0]

    total_pnl = sum(t["pnl"] or 0 for t in trades)
    avg_win = sum(t["pnl"] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t["pnl"] for t in losers) / len(losers) if losers else 0
    win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0

    # Biggest win and loss
    biggest_win = max(trades, key=lambda t: t["pnl"] or 0) if trades else None
    biggest_loss = min(trades, key=lambda t: t["pnl"] or 0) if trades else None

    # Profit factor
    gross_profit = sum(t["pnl"] for t in winners) if winners else 0
    gross_loss = abs(sum(t["pnl"] for t in losers)) if losers else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    # SL vs TP exits
    sl_exits = len([t for t in trades if t["exit_reason"] == "STOP_LOSS"])
    tp_exits = len([t for t in trades if t["exit_reason"] == "TAKE_PROFIT"])

    conn.close()

    return {
        "total_trades": total_trades,
        "winners": len(winners),
        "losers": len(losers),
        "breakeven": len(breakeven),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "biggest_win": dict(biggest_win) if biggest_win else None,
        "biggest_loss": dict(biggest_loss) if biggest_loss else None,
        "profit_factor": round(profit_factor, 2),
        "sl_exits": sl_exits,
        "tp_exits": tp_exits,
    }


def send_performance_report():
    """Send weekly performance report to Telegram."""
    from bot.telegram_bot import send_message

    stats = calculate_performance_stats()

    if not stats:
        return

    pnl_icon = "🟢" if stats["total_pnl"] >= 0 else "🔴"

    big_win_text = ""
    if stats["biggest_win"]:
        big_win_text = f"\n🏆 Best trade: {stats['biggest_win']['ticker']} (${stats['biggest_win']['pnl']:+.2f})"

    big_loss_text = ""
    if stats["biggest_loss"]:
        big_loss_text = f"\n💀 Worst trade: {stats['biggest_loss']['ticker']} (${stats['biggest_loss']['pnl']:+.2f})"

    msg = f"""📊 <b>EDGESIGNAL PERFORMANCE REPORT</b>
━━━━━━━━━━━━━━━━━━━━

{pnl_icon} <b>Total P&L: ${stats['total_pnl']:+.2f}</b>

📈 <b>Statistics:</b>
  Total trades: {stats['total_trades']}
  Win rate: {stats['win_rate']}%
  Winners: {stats['winners']} | Losers: {stats['losers']}
  Avg win: ${stats['avg_win']:+.2f}
  Avg loss: ${stats['avg_loss']:+.2f}
  Profit factor: {stats['profit_factor']}x

🎯 Take profits hit: {stats['tp_exits']}
🛑 Stop losses hit: {stats['sl_exits']}
{big_win_text}{big_loss_text}

#EdgeSignal #Performance"""

    send_message(msg)
    print("[PERFORMANCE] Report sent to Telegram.")


def init_performance_table():
    """Create the performance tracking table."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            signal_type TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl REAL,
            pnl_pct REAL,
            exit_reason TEXT,
            closed_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_perf_ticker ON signal_performance(ticker);
    """)
    conn.commit()
    conn.close()
    print("[PERFORMANCE] Performance table initialized.")


if __name__ == "__main__":
    init_performance_table()
    stats = calculate_performance_stats()
    if stats:
        print(f"\n📊 Performance Stats:")
        print(f"  Total trades: {stats['total_trades']}")
        print(f"  Win rate: {stats['win_rate']}%")
        print(f"  Total P&L: ${stats['total_pnl']:+.2f}")
        print(f"  Profit factor: {stats['profit_factor']}x")
    else:
        print("No closed trades yet.")