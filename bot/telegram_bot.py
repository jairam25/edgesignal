import json
from datetime import datetime
from config.settings import settings


def send_message(text, parse_mode="HTML"):
    """Send a message to the Telegram channel."""
    token = settings.TELEGRAM_BOT_TOKEN or ""
    channel_id = settings.TELEGRAM_CHANNEL_ID or ""

    if not token or not channel_id:
        print("[TELEGRAM] Bot token or channel ID not configured.")
        return False

    try:
        import requests

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[TELEGRAM] Send failed: {e}")
        return False


def broadcast_analysis(analysis_result):
    """Broadcast analysis results to Telegram and Email.

    Sends formatted Telegram messages for each signal, then
    follows up with an email briefing including portfolio info.
    """
    sigs = analysis_result.get("signals", [])
    if not sigs:
        print("[TELEGRAM] No signals to broadcast.")
        return

    # ---- Telegram broadcast ----
    _broadcast_telegram(analysis_result, sigs)

    # ---- Email briefing ----
    _broadcast_email(analysis_result, sigs)


def _broadcast_telegram(analysis_result, sigs):
    """Send Telegram signals."""
    # Send summary header
    header = f"""📊 <b>EDGESIGNAL PRE-MARKET ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━
{analysis_result.get('market_summary', '')[:200]}
"""

    send_message(header)

    # Send each signal
    for s in sigs:
        icon = "🟢" if s.get("signal_type") == "BUY" else "🔴" if s.get("signal_type") == "SELL" else "⚪"
        xasset = s.get("asset_type", "stock")
        msg = f"""{icon} <b>{s.get('signal_type', 'ALERT')} | {s.get('ticker', '')}</b> ({xasset})
━━━━━━━━━━━━━━━━━━━━
<b>{s.get('headline', '')}</b>

{s.get('analysis', '')}

📈 Entry: ${s.get('entry_price', 'N/A')}
🛑 Stop: ${s.get('stop_loss', 'N/A')}
🎯 Target: ${s.get('take_profit', 'N/A')}
⏱ Timeframe: {s.get('timeframe', 'N/A')}
📊 Confidence: {s.get('confidence', 0)}%

#{s.get('ticker', '').replace(' ', '')} #EdgeSignal"""
        send_message(msg)

    # Send risk / cross-asset
    if analysis_result.get("risk_warnings"):
        send_message(f"⚠️ <b>RISK WARNINGS</b>\n{analysis_result['risk_warnings']}")

    if analysis_result.get("cross_asset_insights"):
        send_message(f"🔗 <b>CROSS-ASSET INSIGHTS</b>\n{analysis_result['cross_asset_insights']}")

    print(f"[TELEGRAM] Broadcast {len(sigs)} signals.")


def _broadcast_email(analysis_result, sigs):
    """Send email briefing after Telegram broadcast."""
    try:
        from services.email_alerts import send_daily_briefing, send_signal_alert
        from services.portfolio import get_portfolio_summary

        portfolio_summary = get_portfolio_summary()
        send_daily_briefing(analysis_result, portfolio_summary)

        for signal in sigs:
            if signal.get("confidence", 0) >= 80:
                send_signal_alert(signal)

        print(f"[EMAIL] Briefing sent with {len(sigs)} signals.")
    except Exception as e:
        print(f"  [EMAIL] Briefing failed: {e}")


if __name__ == "__main__":
    # Test
    test_result = {
        "market_summary": "Markets are mixed with tech showing strength.",
        "signals": [
            {
                "ticker": "AAPL",
                "signal_type": "BUY",
                "asset_type": "stock",
                "confidence": 82,
                "headline": "Apple breakout above 190",
                "analysis": "Strong momentum on daily chart.",
                "entry_price": 190.50,
                "stop_loss": 185.00,
                "take_profit": 200.00,
                "timeframe": "swing_2_5_days",
            }
        ],
        "cross_asset_insights": "Tech and crypto showing positive correlation.",
        "risk_warnings": "FOMC minutes this week.",
    }
    broadcast_analysis(test_result)