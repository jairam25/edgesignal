import requests
import json
from datetime import datetime
from core.database import get_connection
from config.settings import settings


TELEGRAM_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


def send_message(text, parse_mode="HTML"):
    """Send a message to the Telegram channel."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
        print("[ERROR] Telegram credentials not set in .env")
        return False

    try:
        response = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHANNEL_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = response.json()

        if data.get("ok"):
            return True
        else:
            print(f"[ERROR] Telegram: {data.get('description', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False


def format_signal(signal):
    """Format a single signal as a Telegram message."""
    icons = {
        "BUY": "🟢",
        "SELL": "🔴",
        "ALERT": "🟡",
        "EDGE": "💎",
    }
    asset_icons = {
        "stock": "📈",
        "crypto": "🪙",
        "commodity": "🛢",
        "polymarket": "🎯",
        "macro": "🏛",
    }

    signal_icon = icons.get(signal.get("signal_type", ""), "⚪")
    asset_icon = asset_icons.get(signal.get("asset_type", ""), "📊")

    confidence = signal.get("confidence", 0)
    conf_bar = "█" * (confidence // 10) + "░" * (10 - confidence // 10)

    msg = f"""{signal_icon} <b>EDGESIGNAL {signal.get('signal_type', 'ALERT')}</b> {asset_icon}

<b>{signal.get('ticker', 'N/A')}</b> — {signal.get('headline', '')}

{signal.get('analysis', '')}

<b>Confidence:</b> {conf_bar} {confidence}%
<b>Type:</b> {signal.get('asset_type', 'N/A').upper()}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

#EdgeSignal #{signal.get('ticker', '').replace('/', '').replace('-', '')} #{signal.get('signal_type', '')}"""

    return msg


def format_market_summary(analysis_result):
    """Format the market summary as a Telegram message."""
    summary = analysis_result.get("market_summary", "No data")
    cross = analysis_result.get("cross_asset_insights", "")
    risks = analysis_result.get("risk_warnings", "")
    signals = analysis_result.get("signals", [])

    # Quick stats
    buys = len([s for s in signals if s["signal_type"] == "BUY"])
    sells = len([s for s in signals if s["signal_type"] == "SELL"])
    alerts = len([s for s in signals if s["signal_type"] in ("ALERT", "EDGE")])

    msg = f"""📊 <b>EDGESIGNAL DAILY BRIEF</b>
━━━━━━━━━━━━━━━━━━━━

{summary}

<b>Signals Generated:</b>
🟢 {buys} BUY  |  🔴 {sells} SELL  |  🟡 {alerts} ALERT

━━━━━━━━━━━━━━━━━━━━
🔗 <b>Cross-Asset Insights</b>
{cross[:500] if cross else 'None detected'}

━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Risk Warnings</b>
{risks[:500] if risks else 'None'}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
#EdgeSignal #DailyBrief"""

    return msg


def broadcast_analysis(analysis_result):
    """Send full analysis to Telegram channel."""
    if not analysis_result:
        print("[TELEGRAM] No analysis to broadcast.")
        return

    print(f"\n[TELEGRAM] Broadcasting to channel...")

    # Send market summary first
    summary_msg = format_market_summary(analysis_result)
    if send_message(summary_msg):
        print("  ✅ Market summary sent")
    else:
        print("  ❌ Market summary failed")
        return

    # Send each signal
    signals = analysis_result.get("signals", [])
    sent = 0
    for signal in signals:
        confidence = signal.get("confidence", 0)

        # Only broadcast signals above threshold
        if confidence < settings.SIGNAL_CONFIDENCE_THRESHOLD:
            continue

        msg = format_signal(signal)
        if send_message(msg):
            sent += 1
            mark_signal_sent(signal)
        else:
            print(f"  ❌ Failed: {signal.get('ticker')}")

        # Telegram rate limit: max 20 messages per minute to a channel
        import time
        time.sleep(3)

    print(f"[TELEGRAM] Done — {sent}/{len(signals)} signals broadcast.")


def mark_signal_sent(signal):
    """Mark a signal as sent in the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE signals
            SET sent_to_telegram = 1
            WHERE ticker = ? AND signal_type = ? AND sent_to_telegram = 0
            ORDER BY created_at DESC
            LIMIT 1
        """, (signal.get("ticker", ""), signal.get("signal_type", "")))
        conn.commit()
        conn.close()
    except Exception:
        pass


def send_test_message():
    """Send a test message to verify bot works."""
    print("\n[TELEGRAM] Sending test message...")

    test_msg = f"""🧪 <b>EDGESIGNAL TEST</b>

✅ Bot is connected and working!
📡 Channel: {settings.TELEGRAM_CHANNEL_ID}
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your EdgeSignal pipeline is ready.
Stocks ✅ Crypto ✅ Commodities ✅ Macro ✅ Polymarket ✅ Sentiment ✅ AI ✅"""

    if send_message(test_msg):
        print("  ✅ Test message sent! Check your Telegram channel.")
    else:
        print("  ❌ Test failed. Check your bot token and channel ID.")


if __name__ == "__main__":
    send_test_message()