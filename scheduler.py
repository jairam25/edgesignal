import time
from datetime import datetime, timedelta
import pytz
from core.database import init_db, get_connection
from config.settings import settings


ET = pytz.timezone("US/Eastern")

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
PREMARKET_START_MIN = 15  # start 15 min before open


def get_et_now():
    """Get current time in Eastern."""
    return datetime.now(ET)


def is_weekday():
    """Check if today is a trading day (Mon-Fri)."""
    return get_et_now().weekday() < 5


def get_premarket_window():
    """Get today's pre-market analysis window (9:15 - 9:30 ET)."""
    now = get_et_now()
    start = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN - PREMARKET_START_MIN, second=0, microsecond=0)
    end = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0, microsecond=0)
    return start, end


def is_in_premarket_window():
    """Check if we're in the 15-min pre-market window."""
    now = get_et_now()
    start, end = get_premarket_window()
    return start <= now <= end


def run_safe(name, func):
    """Run a function with error handling."""
    try:
        return func()
    except Exception as e:
        print(f"[ERROR] {name} failed: {e}")
        return None


def fetch_all_data():
    """Fetch fresh data from all sources."""
    from services.market_data import fetch_all_market_data
    from services.crypto_data import fetch_crypto
    from services.commodity_data import fetch_commodities
    from services.macro_data import fetch_macro
    from services.polymarket import fetch_polymarket
    from services.sentiment import fetch_sentiment

    print(f"\n{'='*60}")
    print(f"🔄 DATA REFRESH — {get_et_now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print(f"{'='*60}")

    run_safe("Market Data", fetch_all_market_data)
    run_safe("Crypto", fetch_crypto)
    run_safe("Commodities", fetch_commodities)
    run_safe("Macro", fetch_macro)
    run_safe("Polymarket", fetch_polymarket)
    run_safe("Sentiment", fetch_sentiment)

    from services.portfolio import update_all_positions
    run_safe("Portfolio Update", update_all_positions)

    print(f"\n✅ All data sources refreshed.")


def run_premarket_analysis(minute_number):
    """Run the pre-market AI analysis with previous day + current data."""
    from services.analyst import run_premarket_analysis
    from bot.telegram_bot import broadcast_analysis, send_message

    print(f"\n{'='*60}")
    print(f"🧠 PRE-MARKET ANALYSIS — Minute {minute_number}/15")
    print(f"   {get_et_now().strftime('%H:%M:%S ET')} — Market opens in {15 - minute_number} min")
    print(f"{'='*60}")

    result = run_premarket_analysis(minute_number)

    if result:
        if minute_number == 1:
            # First minute: send full briefing
            broadcast_analysis(result)
            # Auto-create positions from signals
            from services.portfolio import create_position_from_signal
            for signal in result.get("signals", []):
                create_position_from_signal(signal)
        elif result.get("signals"):
            # Subsequent minutes: only send if new/updated signals
            from bot.telegram_bot import format_signal, send_message
            header = f"""⏱ <b>MINUTE {minute_number}/15 UPDATE</b>
🕐 Market opens in {15 - minute_number} min
━━━━━━━━━━━━━━━━━━━━"""
            send_message(header)

            for signal in result.get("signals", []):
                if signal.get("confidence", 0) >= settings.SIGNAL_CONFIDENCE_THRESHOLD:
                    msg = format_signal(signal)
                    send_message(msg)
                    time.sleep(2)
    else:
        print("[SCHEDULER] No analysis result.")


def send_daily_recap():
    """Send end-of-day performance recap."""
    from bot.telegram_bot import send_message

    conn = get_connection()
    cursor = conn.cursor()

    # Get today's signals
    cursor.execute("""
        SELECT ticker, signal_type, confidence, headline
        FROM signals
        WHERE DATE(created_at) = DATE('now')
        ORDER BY confidence DESC
    """)
    signals = cursor.fetchall()

    # Get today's top movers
    cursor.execute("""
        SELECT ticker, price, change_pct
        FROM market_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices)
        ORDER BY ABS(change_pct) DESC
        LIMIT 10
    """)
    movers = cursor.fetchall()
    conn.close()

    if not signals and not movers:
        return

    movers_text = ""
    for m in movers:
        icon = "🟢" if m["change_pct"] >= 0 else "🔴"
        movers_text += f"\n  {icon} {m['ticker']}: ${m['price']:,.2f} ({m['change_pct']:+.2f}%)"

    signals_text = ""
    for s in signals:
        icon = {"BUY": "🟢", "SELL": "🔴", "ALERT": "🟡", "EDGE": "💎"}.get(s["signal_type"], "⚪")
        signals_text += f"\n  {icon} [{s['signal_type']}] {s['ticker']} ({s['confidence']}%) — {s['headline']}"

    msg = f"""📋 <b>EDGESIGNAL DAILY RECAP</b>
━━━━━━━━━━━━━━━━━━━━

<b>📊 Top Movers Today:</b>{movers_text}

<b>🚨 Signals Generated:</b>{signals_text if signals_text else chr(10) + '  No signals today'}

🕐 {get_et_now().strftime('%Y-%m-%d %H:%M ET')}
#EdgeSignal #DailyRecap"""

    # Send portfolio update too
    from services.portfolio import send_portfolio_update, auto_close_stale_positions
    auto_close_stale_positions(max_days=5)
    send_portfolio_update()

    send_message(msg)
    print("[SCHEDULER] Daily recap sent.")


def scheduler_loop():
    """Main loop — runs pre-market analysis 15 min before open."""
    print(f"""
╔══════════════════════════════════════════════════════════╗
║            🚀 EDGESIGNAL ENGINE v{settings.VERSION}                  ║
║                                                          ║
║  Mode: PRE-MARKET INTELLIGENCE                           ║
║  Window: 9:15 AM - 9:30 AM ET (15 min before open)      ║
║  Updates: Every 60 seconds during window                 ║
║  Signal threshold: {settings.SIGNAL_CONFIDENCE_THRESHOLD}%                                ║
║                                                          ║
║  Stocks  ✅  Crypto    ✅  Commodities ✅               ║
║  Macro   ✅  Polymarket ✅  Sentiment  ✅               ║
║  AI Brain ✅  Telegram  ✅                               ║
╚══════════════════════════════════════════════════════════╝
    """)

    premarket_ran_today = False
    recap_sent_today = False
    last_date = None

    while True:
        try:
            now = get_et_now()
            today = now.date()

            # Reset flags on new day
            if last_date != today:
                premarket_ran_today = False
                recap_sent_today = False
                last_date = today

            # Skip weekends
            if not is_weekday():
                print(f"\r⏸  Weekend — next session Monday. Sleeping... ({now.strftime('%H:%M ET')})", end="", flush=True)
                time.sleep(3600)
                continue

            # PRE-MARKET WINDOW: 9:15 - 9:30 ET
            if is_in_premarket_window() and not premarket_ran_today:
                print(f"\n\n🔔 PRE-MARKET WINDOW OPEN — {now.strftime('%H:%M:%S ET')}")
                print(f"   Running 15-minute analysis sequence...\n")

                # Initial data fetch
                fetch_all_data()

                # Run analysis every minute for 15 minutes
                for minute in range(1, 16):
                    current = get_et_now()

                    # Check we haven't passed market open
                    _, market_open = get_premarket_window()
                    if current >= market_open:
                        print(f"\n🔔 MARKET OPEN — {current.strftime('%H:%M:%S ET')}")
                        break

                    print(f"\n⏱  Minute {minute}/15 — {current.strftime('%H:%M:%S ET')}")

                    # Refresh data every 3 minutes during window
                    if minute % 3 == 0:
                        fetch_all_data()

                    # Run AI analysis every minute
                    run_premarket_analysis(minute)

                    # Wait for next minute
                    if minute < 15:
                        elapsed = (get_et_now() - current).total_seconds()
                        sleep_time = max(60 - elapsed, 5)
                        print(f"   Next update in {int(sleep_time)}s...")
                        time.sleep(sleep_time)

                premarket_ran_today = True
                print(f"\n✅ Pre-market sequence complete. Signals delivered.")

            # END OF DAY RECAP: 4:05 PM ET
            elif now.hour == 16 and now.minute >= 5 and not recap_sent_today:
                print(f"\n📋 Sending daily recap...")
                fetch_all_data()  # Get final closing data
                send_daily_recap()
                recap_sent_today = True

            # WAITING MODE
            else:
                start, _ = get_premarket_window()
                if now < start:
                    wait_seconds = (start - now).total_seconds()
                    hours = int(wait_seconds // 3600)
                    mins = int((wait_seconds % 3600) // 60)
                    status = f"Pre-market in {hours}h {mins}m"
                elif premarket_ran_today:
                    status = "Today's analysis complete"
                else:
                    status = "Waiting for next window"

                print(f"\r⏳ {status} | {now.strftime('%H:%M ET')} | Ctrl+C to stop", end="", flush=True)
                time.sleep(30)

        except KeyboardInterrupt:
            print(f"\n\n🛑 EdgeSignal stopped at {get_et_now().strftime('%H:%M:%S ET')}")
            break
        except Exception as e:
            print(f"\n[ERROR] Scheduler: {e}")
            time.sleep(60)


if __name__ == "__main__":
    init_db()
    scheduler_loop()