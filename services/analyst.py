import json
import time
from datetime import datetime
from config.settings import settings

# ---------------------------------------------------------------------------
# DeepSeek API helper (using requests – no extra SDK needed)
# ---------------------------------------------------------------------------
try:
    import requests as _requests

    def _deepseek_chat(messages, model="deepseek-chat", temperature=0.3, max_tokens=2048):
        """Send a chat completion request to DeepSeek."""
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            print("[ANALYST] DeepSeek API key not configured.")
            return ""

        resp = _requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

except ImportError:
    _requests = None

    def _deepseek_chat(*args, **kwargs):
        print("[ANALYST] requests library not installed. Cannot call DeepSeek.")
        return ""


# ---------------------------------------------------------------------------
# Helper: get current market data snapshot
# ---------------------------------------------------------------------------
def _fetch_market_snapshot():
    """
    Fetch a quick snapshot of market conditions:
    - S&P 500 / Nasdaq / Dow price & daily change
    - VIX
    - US 10Y yield
    - Top active stock tickers
    Returns a dict for the AI prompt.
    """
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "indices": {},
        "top_movers_stocks": [],
    }

    # Use yfinance for quick index data (lightweight, no complex parsing)
    try:
        import yfinance as yf

        index_tickers = {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "Dow Jones": "^DJI",
            "VIX": "^VIX",
            "10Y Yield": "^TNX",
        }

        for name, symbol in index_tickers.items():
            try:
                t = yf.Ticker(symbol)
                data = t.history(period="2d")
                if len(data) >= 2:
                    prev_close = float(data["Close"].iloc[-2])
                    current = float(data["Close"].iloc[-1])
                    change_pct = round(((current - prev_close) / prev_close) * 100, 2)
                    snapshot["indices"][name] = {
                        "price": round(current, 2),
                        "change_pct": change_pct,
                    }
                elif len(data) == 1:
                    snapshot["indices"][name] = {
                        "price": round(float(data["Close"].iloc[-1]), 2),
                        "change_pct": 0.0,
                    }
            except Exception:
                continue

        # Get a few active tickers (from config/assets if available)
        try:
            from config.assets import ALL_STOCK_TICKERS
            snapshot["top_movers_stocks"] = list(ALL_STOCK_TICKERS[:15])
        except ImportError:
            snapshot["top_movers_stocks"] = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "META",
                "NVDA", "TSLA", "AMD", "INTC", "BA",
            ]

    except Exception as e:
        print(f"[ANALYST] Market snapshot fetch error: {e}")

    return snapshot


# ---------------------------------------------------------------------------
# Main: run_premarket_analysis()
# ---------------------------------------------------------------------------
def run_premarket_analysis(send_email=True, send_telegram=True):
    """
    Full pre-market analysis pipeline:
    1. Fetch current market data snapshot
    2. Run multi-timeframe technical scan on top movers
    3. Feed MTF results + market data into DeepSeek AI
    4. Parse and return signals/analysis
    5. (Optional) Send results via email and Telegram
    """
    print(f"\n{'='*60}")
    print(f"[ANALYST] Pre-Market Analysis — {datetime.now()}")
    print(f"{'='*60}")

    # ---- Step 1: Market snapshot ----
    print("[ANALYST] Fetching market snapshot...")
    current_data = _fetch_market_snapshot()

    # ---- Step 2: Multi-Timeframe analysis ----
    print("[ANALYST] Running MTF scan...")
    mtf_data = []
    try:
        from services.multi_timeframe import run_multi_timeframe_scan, get_mtf_summary_for_ai
        run_multi_timeframe_scan(tickers=current_data.get('top_movers_stocks', [])[:10])
        mtf_data = get_mtf_summary_for_ai()
    except Exception as e:
        print(f"[ANALYST] MTF scan failed: {e}")

    # ---- Step 3: Build AI prompt ----
    market_json = json.dumps(current_data.get("indices", {}), indent=2)
    mtf_json = json.dumps(mtf_data[:10], indent=2)

    user_prompt = f"""You are an expert financial analyst AI for EdgeSignal. Analyze the market and generate trading signals.

=== MARKET DATA ===
{market_json}

=== MULTI-TIMEFRAME TECHNICAL ANALYSIS ===
{mtf_json}

=== INSTRUCTIONS ===
Based on the market data and multi-timeframe technical analysis above, provide:
1. A concise market summary (2-3 sentences)
2. Top 3-5 trading signals with:
   - ticker
   - signal_type (BUY / SELL / NEUTRAL)
   - confidence (0-100)
   - headline (short description)
   - analysis (1-2 sentences explaining the reasoning)
   - entry_price (approximate)
   - stop_loss (approximate)
   - take_profit (approximate)
   - timeframe (e.g. "swing_2_5_days", "day_trade", "position_1_2_weeks")
3. Cross-asset insights (any correlations or macro signals)
4. Risk warnings (any concerns like FOMC, earnings, geopolitical)

Return your response as valid JSON with this exact structure:
{{
  "market_summary": "...",
  "signals": [
    {{
      "ticker": "...",
      "signal_type": "BUY",
      "confidence": 80,
      "headline": "...",
      "analysis": "...",
      "entry_price": 0.0,
      "stop_loss": 0.0,
      "take_profit": 0.0,
      "timeframe": "swing_2_5_days"
    }}
  ],
  "cross_asset_insights": "...",
  "risk_warnings": "..."
}}"""

    system_prompt = "You are a professional quantitative financial analyst. Respond ONLY with valid JSON. No markdown fences, no commentary."

    # ---- Step 4: Call DeepSeek ----
    print("[ANALYST] Calling DeepSeek API...")
    analysis_result = None

    try:
        raw_response = _deepseek_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="deepseek-chat",
            temperature=0.3,
            max_tokens=2048,
        )

        if raw_response:
            # Try to parse the JSON response
            # Strip markdown fences if present
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first and last fence lines
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            analysis_result = json.loads(cleaned)
            print("[ANALYST] DeepSeek response parsed successfully.")

            # Print summary
            print(f"\n  📊 Market: {analysis_result.get('market_summary', 'N/A')[:120]}...")
            sigs = analysis_result.get("signals", [])
            for s in sigs:
                icon = "🟢" if s.get("signal_type") == "BUY" else "🔴" if s.get("signal_type") == "SELL" else "⚪"
                print(f"  {icon} {s.get('ticker')}: {s.get('headline', '')} ({s.get('confidence', 0)}%)")

        else:
            print("[ANALYST] Empty response from DeepSeek.")
            analysis_result = {
                "market_summary": "Analysis unavailable.",
                "signals": [],
                "cross_asset_insights": "",
                "risk_warnings": "",
            }

    except json.JSONDecodeError as e:
        print(f"[ANALYST] Failed to parse DeepSeek JSON: {e}")
        print(f"  Raw: {raw_response[:500] if raw_response else 'None'}")
        analysis_result = {
            "market_summary": "AI parsing error.",
            "signals": [],
            "cross_asset_insights": "",
            "risk_warnings": "",
        }
    except Exception as e:
        print(f"[ANALYST] DeepSeek API error: {e}")
        analysis_result = {
            "market_summary": f"API error: {e}",
            "signals": [],
            "cross_asset_insights": "",
            "risk_warnings": "",
        }

    # ---- Step 5: Save to database ----
    _save_analysis_to_db(current_data, mtf_data, analysis_result)

    # ---- Step 6: Deliver results ----
    # Email
    if send_email and analysis_result.get("signals"):
        try:
            from services.email_alerts import send_daily_briefing
            sent = send_daily_briefing(analysis_result)
            if sent:
                print("[ANALYST] Daily briefing emailed.")
        except Exception as e:
            print(f"[ANALYST] Email delivery failed: {e}")

    # Telegram
    if send_telegram and analysis_result.get("signals"):
        try:
            _send_telegram_signals(analysis_result)
        except Exception as e:
            print(f"[ANALYST] Telegram delivery failed: {e}")

    print(f"[ANALYST] Pre-market analysis complete.")
    return analysis_result


# ---------------------------------------------------------------------------
# Save analysis to SQLite
# ---------------------------------------------------------------------------
def _save_analysis_to_db(market_data, mtf_data, analysis_result):
    try:
        from core.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Create tables if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_snapshot TEXT,
                mtf_data TEXT,
                signals TEXT,
                market_summary TEXT,
                cross_asset_insights TEXT,
                risk_warnings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO ai_analysis
            (market_snapshot, mtf_data, signals, market_summary, cross_asset_insights, risk_warnings)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            json.dumps(market_data.get("indices", {})),
            json.dumps(mtf_data),
            json.dumps(analysis_result.get("signals", [])),
            analysis_result.get("market_summary", ""),
            analysis_result.get("cross_asset_insights", ""),
            analysis_result.get("risk_warnings", ""),
        ))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ANALYST] DB save error: {e}")


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------
def _send_telegram_signals(analysis_result):
    try:
        from bot.telegram_bot import send_message

        sigs = analysis_result.get("signals", [])
        if not sigs:
            return

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

    except Exception as e:
        print(f"[ANALYST] Telegram send error: {e}")


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = run_premarket_analysis(send_email=False, send_telegram=False)
    print("\n" + "=" * 60)
    print(json.dumps(result, indent=2, default=str))