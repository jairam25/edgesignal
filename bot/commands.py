import json
import threading
import time
from datetime import datetime
from core.database import get_connection
from config.settings import settings

try:
    import telebot
except ImportError:
    telebot = None


def start_command_bot():
    """Start the Telegram command bot in a separate thread."""
    if not telebot:
        print("[BOT] telebot not installed. Run: pip install pyTelegramBotAPI")
        return

    if not settings.TELEGRAM_BOT_TOKEN:
        print("[BOT] TELEGRAM_BOT_TOKEN not set.")
        return

    bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN)

    @bot.message_handler(commands=["start", "help"])
    def cmd_help(message):
        bot.reply_to(message, """🚀 <b>EdgeSignal Bot Commands</b>
━━━━━━━━━━━━━━━━━━━━

📊 <b>Market Data</b>
/status — System status & last update
/price AAPL — Get latest price for a ticker
/top — Top gainers & losers
/crypto — Crypto prices

💼 <b>Portfolio</b>
/portfolio — All open positions with P&L
/pnl — Total P&L summary
/open BUY AAPL 150.00 10 — Open position (side ticker price qty)
/close AAPL — Close a position

🧠 <b>AI Analysis</b>
/analyze — Force AI analysis now
/signals — Latest AI signals
/history — Signal history (last 7 days)

🎯 <b>Polymarket</b>
/poly — Top Polymarket contracts

⚙️ <b>System</b>
/refresh — Force data refresh now
/stats — Database stats""", parse_mode="HTML")

    @bot.message_handler(commands=["status"])
    def cmd_status(message):
        conn = get_connection()
        cursor = conn.cursor()

        stock_time = cursor.execute("SELECT MAX(fetched_at) as t FROM market_prices").fetchone()["t"]
        crypto_time = cursor.execute("SELECT MAX(fetched_at) as t FROM crypto_prices").fetchone()["t"]
        signal_count = cursor.execute("SELECT COUNT(*) as c FROM signals WHERE DATE(created_at) = DATE('now')").fetchone()["c"]
        open_pos = cursor.execute("SELECT COUNT(*) as c FROM portfolio WHERE status = 'OPEN'").fetchone()["c"]

        conn.close()

        bot.reply_to(message, f"""⚡ <b>EdgeSignal Status</b>
━━━━━━━━━━━━━━━━━━━━

🟢 System: <b>Online</b>
📈 Last stock update: {stock_time or 'Never'}
🪙 Last crypto update: {crypto_time or 'Never'}
🚨 Signals today: {signal_count}
💼 Open positions: {open_pos}
🕐 Server time: {datetime.now().strftime('%H:%M:%S UTC')}""", parse_mode="HTML")

    @bot.message_handler(commands=["price"])
    def cmd_price(message):
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /price AAPL")
            return

        ticker = parts[1].upper()
        conn = get_connection()
        cursor = conn.cursor()

        # Check stocks
        row = cursor.execute(
            "SELECT ticker, price, change_pct, volume, fetched_at FROM market_prices WHERE ticker = ? ORDER BY fetched_at DESC LIMIT 1",
            (ticker,)
        ).fetchone()

        if not row:
            # Check crypto
            pair = f"{ticker}/USDT"
            row = cursor.execute(
                "SELECT pair as ticker, price, change_pct_24h as change_pct, volume_24h as volume, fetched_at FROM crypto_prices WHERE pair = ? ORDER BY fetched_at DESC LIMIT 1",
                (pair,)
            ).fetchone()

        if not row:
            # Check commodities
            row = cursor.execute(
                "SELECT name as ticker, price, change_pct, volume, fetched_at FROM commodity_prices WHERE ticker = ? OR name = ? ORDER BY fetched_at DESC LIMIT 1",
                (ticker, ticker)
            ).fetchone()

        conn.close()

        if row:
            change = row["change_pct"] or 0
            icon = "🟢" if change >= 0 else "🔴"
            vol = row["volume"] or 0
            vol_str = f"{vol/1e6:.1f}M" if vol > 1e6 else f"{vol/1e3:.0f}K" if vol > 1e3 else str(vol)

            bot.reply_to(message, f"""{icon} <b>{row['ticker']}</b>

💰 Price: <b>${row['price']:,.2f}</b>
📊 Change: <b>{change:+.2f}%</b>
📦 Volume: {vol_str}
🕐 Updated: {row['fetched_at']}""", parse_mode="HTML")
        else:
            bot.reply_to(message, f"❌ Ticker '{ticker}' not found.")

    @bot.message_handler(commands=["top"])
    def cmd_top(message):
        conn = get_connection()
        cursor = conn.cursor()

        gainers = cursor.execute("""
            SELECT ticker, price, change_pct FROM market_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
            ORDER BY change_pct DESC LIMIT 5
        """).fetchall()

        losers = cursor.execute("""
            SELECT ticker, price, change_pct FROM market_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices) AND change_pct IS NOT NULL
            ORDER BY change_pct ASC LIMIT 5
        """).fetchall()

        conn.close()

        text = "📊 <b>Top Movers</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🟢 <b>Gainers</b>\n"
        for g in gainers:
            text += f"  {g['ticker']}: ${g['price']:,.2f} ({g['change_pct']:+.2f}%)\n"

        text += "\n🔴 <b>Losers</b>\n"
        for l in losers:
            text += f"  {l['ticker']}: ${l['price']:,.2f} ({l['change_pct']:+.2f}%)\n"

        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["crypto"])
    def cmd_crypto(message):
        conn = get_connection()
        rows = conn.execute("""
            SELECT pair, price, change_pct_24h FROM crypto_prices
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM crypto_prices)
            ORDER BY market_cap DESC
        """).fetchall()
        conn.close()

        text = "🪙 <b>Crypto Prices</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for r in rows:
            change = r["change_pct_24h"] or 0
            icon = "🟢" if change >= 0 else "🔴"
            text += f"{icon} {r['pair']}: ${r['price']:,.2f} ({change:+.2f}%)\n"

        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["portfolio"])
    def cmd_portfolio(message):
        conn = get_connection()
        positions = conn.execute("""
            SELECT ticker, side, entry_price, current_price, quantity, pnl, pnl_pct
            FROM portfolio WHERE status = 'OPEN' ORDER BY pnl DESC
        """).fetchall()
        conn.close()

        if not positions:
            bot.reply_to(message, "💼 No open positions.")
            return

        total_pnl = sum(p["pnl"] or 0 for p in positions)
        total_icon = "🟢" if total_pnl >= 0 else "🔴"

        text = f"""💼 <b>Portfolio</b>
━━━━━━━━━━━━━━━━━━━━

{total_icon} Total P&L: <b>${total_pnl:+.2f}</b>
📊 Positions: {len(positions)}

"""
        for p in positions:
            pnl = p["pnl"] or 0
            pnl_pct = p["pnl_pct"] or 0
            icon = "🟢" if pnl >= 0 else "🔴"
            text += f"""{icon} <b>{p['ticker']}</b> ({p['side']})
  Entry: ${p['entry_price']:,.2f} → Now: ${p['current_price']:,.2f}
  Qty: {p['quantity']:.4f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)

"""

        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["pnl"])
    def cmd_pnl(message):
        conn = get_connection()
        cursor = conn.cursor()

        open_pnl = cursor.execute("SELECT SUM(pnl) as total FROM portfolio WHERE status = 'OPEN'").fetchone()["total"] or 0
        closed_pnl = cursor.execute("SELECT SUM(pnl) as total FROM portfolio WHERE status = 'CLOSED'").fetchone()["total"] or 0
        open_count = cursor.execute("SELECT COUNT(*) as c FROM portfolio WHERE status = 'OPEN'").fetchone()["c"]
        closed_count = cursor.execute("SELECT COUNT(*) as c FROM portfolio WHERE status = 'CLOSED'").fetchone()["c"]
        winners = cursor.execute("SELECT COUNT(*) as c FROM portfolio WHERE pnl > 0").fetchone()["c"]
        losers = cursor.execute("SELECT COUNT(*) as c FROM portfolio WHERE pnl < 0").fetchone()["c"]

        conn.close()

        total = open_pnl + closed_pnl
        icon = "🟢" if total >= 0 else "🔴"
        win_rate = (winners / (winners + losers) * 100) if (winners + losers) > 0 else 0

        bot.reply_to(message, f"""{icon} <b>P&L Summary</b>
━━━━━━━━━━━━━━━━━━━━

💰 Total P&L: <b>${total:+.2f}</b>
📈 Open P&L: ${open_pnl:+.2f} ({open_count} positions)
📉 Closed P&L: ${closed_pnl:+.2f} ({closed_count} trades)
🏆 Win Rate: {win_rate:.0f}% ({winners}W / {losers}L)""", parse_mode="HTML")

    @bot.message_handler(commands=["open"])
    def cmd_open(message):
        parts = message.text.split()
        if len(parts) < 5:
            bot.reply_to(message, "Usage: /open BUY AAPL 150.00 10\n(side ticker price quantity)")
            return

        try:
            side = parts[1].upper()
            ticker = parts[2].upper()
            price = float(parts[3])
            qty = float(parts[4])
        except (ValueError, IndexError):
            bot.reply_to(message, "❌ Invalid format. Use: /open BUY AAPL 150.00 10")
            return

        if side not in ("BUY", "SELL", "LONG", "SHORT"):
            bot.reply_to(message, "❌ Side must be BUY/SELL or LONG/SHORT")
            return

        side = "LONG" if side in ("BUY", "LONG") else "SHORT"

        conn = get_connection()
        cursor = conn.cursor()

        # Check for existing position
        existing = cursor.execute(
            "SELECT id FROM portfolio WHERE ticker = ? AND status = 'OPEN'", (ticker,)
        ).fetchone()

        if existing:
            bot.reply_to(message, f"❌ Already have an open position for {ticker}")
            conn.close()
            return

        cursor.execute("""
            INSERT INTO portfolio
            (ticker, asset_type, entry_price, current_price, quantity, side, pnl, pnl_pct, status)
            VALUES (?, 'manual', ?, ?, ?, ?, 0, 0, 'OPEN')
        """, (ticker, price, price, qty, side))

        conn.commit()
        conn.close()

        icon = "🟢" if side == "LONG" else "🔴"
        bot.reply_to(message, f"""{icon} <b>Position Opened</b>

📊 {ticker} ({side})
💰 Entry: ${price:,.2f}
📦 Quantity: {qty}
💵 Value: ${price * qty:,.2f}""", parse_mode="HTML")

    @bot.message_handler(commands=["close"])
    def cmd_close(message):
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /close AAPL")
            return

        ticker = parts[1].upper()

        from services.portfolio import close_position, get_latest_price

        price = get_latest_price(ticker)
        result = close_position(ticker, price)

        if result is not None:
            icon = "🟢" if result >= 0 else "🔴"
            bot.reply_to(message, f"""{icon} <b>Position Closed</b>

📊 {ticker}
💰 P&L: <b>${result:+.2f}</b>""", parse_mode="HTML")
        else:
            bot.reply_to(message, f"❌ No open position for {ticker}")

    @bot.message_handler(commands=["signals"])
    def cmd_signals(message):
        conn = get_connection()
        signals = conn.execute("""
            SELECT ticker, signal_type, confidence, headline, created_at
            FROM signals ORDER BY created_at DESC LIMIT 10
        """).fetchall()
        conn.close()

        if not signals:
            bot.reply_to(message, "🚨 No signals yet.")
            return

        text = "🚨 <b>Latest Signals</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for s in signals:
            icon = {"BUY": "🟢", "SELL": "🔴", "ALERT": "🟡", "EDGE": "💎"}.get(s["signal_type"], "⚪")
            text += f"{icon} [{s['signal_type']}] <b>{s['ticker']}</b> ({s['confidence']}%)\n  {s['headline']}\n  {s['created_at']}\n\n"

        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["analyze"])
    def cmd_analyze(message):
        bot.reply_to(message, "🧠 Running AI analysis... This takes ~30 seconds.")

        try:
            from services.market_data import fetch_all_market_data
            from services.crypto_data import fetch_crypto
            from services.commodity_data import fetch_commodities
            from services.analyst import run_analysis
            from bot.telegram_bot import broadcast_analysis

            fetch_all_market_data()
            fetch_crypto()
            fetch_commodities()

            result = run_analysis()
            if result:
                broadcast_analysis(result)
                bot.reply_to(message, f"✅ Analysis complete — {len(result.get('signals', []))} signals generated and broadcast.")
            else:
                bot.reply_to(message, "⚠️ Analysis returned no results.")
        except Exception as e:
            bot.reply_to(message, f"❌ Analysis failed: {str(e)[:200]}")

    @bot.message_handler(commands=["refresh"])
    def cmd_refresh(message):
        bot.reply_to(message, "🔄 Refreshing all data sources...")

        try:
            from services.market_data import fetch_all_market_data
            from services.crypto_data import fetch_crypto
            from services.commodity_data import fetch_commodities
            from services.macro_data import fetch_macro
            from services.polymarket import fetch_polymarket
            from services.sentiment import fetch_sentiment
            from services.portfolio import update_all_positions

            fetch_all_market_data()
            fetch_crypto()
            fetch_commodities()
            fetch_macro()
            fetch_polymarket()
            fetch_sentiment()
            update_all_positions()

            bot.reply_to(message, "✅ All data refreshed & portfolio updated!")
        except Exception as e:
            bot.reply_to(message, f"❌ Refresh failed: {str(e)[:200]}")

    @bot.message_handler(commands=["poly"])
    def cmd_poly(message):
        conn = get_connection()
        rows = conn.execute("""
            SELECT question, market_price, volume FROM polymarket_contracts
            WHERE fetched_at = (SELECT MAX(fetched_at) FROM polymarket_contracts)
            ORDER BY volume DESC LIMIT 10
        """).fetchall()
        conn.close()

        if not rows:
            bot.reply_to(message, "🎯 No Polymarket data.")
            return

        text = "🎯 <b>Top Polymarket Contracts</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for r in rows:
            prob = f"{r['market_price']*100:.0f}%" if r["market_price"] else "N/A"
            vol = f"${r['volume']:,.0f}" if r["volume"] else "$0"
            q = r["question"][:70]
            text += f"[{prob}] {q}\n  Vol: {vol}\n\n"

        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["stats"])
    def cmd_stats(message):
        conn = get_connection()
        cursor = conn.cursor()

        stocks = cursor.execute("SELECT COUNT(*) as c FROM market_prices").fetchone()["c"]
        crypto = cursor.execute("SELECT COUNT(*) as c FROM crypto_prices").fetchone()["c"]
        commodities = cursor.execute("SELECT COUNT(*) as c FROM commodity_prices").fetchone()["c"]
        signals = cursor.execute("SELECT COUNT(*) as c FROM signals").fetchone()["c"]
        poly = cursor.execute("SELECT COUNT(*) as c FROM polymarket_contracts").fetchone()["c"]
        portfolio = cursor.execute("SELECT COUNT(*) as c FROM portfolio").fetchone()["c"]

        conn.close()

        bot.reply_to(message, f"""📊 <b>Database Stats</b>
━━━━━━━━━━━━━━━━━━━━

📈 Stock records: {stocks:,}
🪙 Crypto records: {crypto:,}
🛢 Commodity records: {commodities:,}
🚨 Signals: {signals:,}
🎯 Polymarket contracts: {poly:,}
💼 Portfolio entries: {portfolio:,}""", parse_mode="HTML")

    @bot.message_handler(commands=["performance"])
    def cmd_performance(message):
        from services.performance import calculate_performance_stats

        stats = calculate_performance_stats()
        if not stats:
            bot.reply_to(message, "📊 No closed trades yet.")
            return

        pnl_icon = "🟢" if stats["total_pnl"] >= 0 else "🔴"
        bot.reply_to(message, f"""{pnl_icon} <b>Performance Stats</b>
━━━━━━━━━━━━━━━━━━━━

💰 Total P&L: <b>${stats['total_pnl']:+.2f}</b>
📊 Win Rate: <b>{stats['win_rate']}%</b>
📈 Trades: {stats['total_trades']} ({stats['winners']}W / {stats['losers']}L)
💵 Avg Win: ${stats['avg_win']:+.2f}
💸 Avg Loss: ${stats['avg_loss']:+.2f}
⚡ Profit Factor: {stats['profit_factor']}x
🎯 Take Profits: {stats['tp_exits']}
🛑 Stop Losses: {stats['sl_exits']}""", parse_mode="HTML")

    # Start polling in a thread
    print("[BOT] Starting Telegram command bot...")
    while True:
        try:
            bot.polling(non_stop=True, timeout=60)
        except Exception as e:
            print(f"[BOT] Polling error: {e}")
            time.sleep(10)


def start_bot_thread():
    """Start the command bot in a background thread."""
    thread = threading.Thread(target=start_command_bot, daemon=True)
    thread.start()
    print("[BOT] Command bot thread started.")
    return thread