import json
from datetime import datetime
from openai import OpenAI
from core.database import get_connection
from config.settings import settings


def get_ai_client():
    """Create DeepSeek API client."""
    if not settings.DEEPSEEK_API_KEY:
        print("[ERROR] DEEPSEEK_API_KEY not set in .env")
        return None

    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )


def get_latest_data():
    """Pull latest data from all tables for AI analysis."""
    conn = get_connection()
    cursor = conn.cursor()

    data = {}

    # Latest stock prices
    cursor.execute("""
        SELECT ticker, asset_type, price, change_pct, volume
        FROM market_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM market_prices)
        ORDER BY ABS(change_pct) DESC
        LIMIT 20
    """)
    data["top_movers_stocks"] = [dict(r) for r in cursor.fetchall()]

    # Latest crypto
    cursor.execute("""
        SELECT pair, price, change_pct_24h, volume_24h, market_cap
        FROM crypto_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM crypto_prices)
        ORDER BY ABS(change_pct_24h) DESC
    """)
    data["crypto"] = [dict(r) for r in cursor.fetchall()]

    # Latest commodities
    cursor.execute("""
        SELECT name, ticker, price, change_pct
        FROM commodity_prices
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM commodity_prices)
    """)
    data["commodities"] = [dict(r) for r in cursor.fetchall()]

    # Latest macro
    cursor.execute("""
        SELECT series_name, value, date
        FROM macro_data
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM macro_data)
    """)
    data["macro"] = [dict(r) for r in cursor.fetchall()]

    # Latest Polymarket (top by volume)
    cursor.execute("""
        SELECT question, market_price, volume, liquidity
        FROM polymarket_contracts
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM polymarket_contracts)
        ORDER BY volume DESC
        LIMIT 15
    """)
    data["polymarket"] = [dict(r) for r in cursor.fetchall()]

    # Latest sentiment
    cursor.execute("""
        SELECT ticker, score, post_count, summary
        FROM sentiment
        WHERE fetched_at = (SELECT MAX(fetched_at) FROM sentiment)
        ORDER BY post_count DESC
    """)
    data["sentiment"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return data


SYSTEM_PROMPT = """You are EdgeSignal AI — an elite market analyst monitoring stocks, crypto, commodities, prediction markets, and macro economics in real-time.

Your job is to analyze ALL the data provided and generate actionable trading signals.

RULES:
1. Only generate signals you have HIGH confidence in (70%+ conviction)
2. Every signal must have: asset, direction (BUY/SELL/ALERT), confidence (0-100), and clear reasoning
3. Look for CROSS-ASSET patterns (e.g., oil inventory drop → energy stocks, bond yields → tech stocks)
4. Flag Polymarket contracts where the probability seems mispriced based on other data
5. Factor in sentiment — extreme bullish/bearish sentiment often signals reversals
6. Be specific — name exact tickers, price levels, and timeframes
7. If nothing stands out, say so. Never force a signal.

RESPOND IN THIS EXACT JSON FORMAT:
{
    "market_summary": "2-3 sentence overview of current market conditions",
    "signals": [
        {
            "asset_type": "stock|crypto|commodity|polymarket|macro",
            "ticker": "AAPL",
            "signal_type": "BUY|SELL|ALERT|EDGE",
            "confidence": 75,
            "headline": "Short punchy headline",
            "analysis": "Detailed reasoning with data points"
        }
    ],
    "cross_asset_insights": "Any patterns connecting different markets",
    "risk_warnings": "Key risks to watch"
}

Return ONLY valid JSON. No markdown, no backticks, no extra text."""


def run_analysis():
    """Run full AI analysis on latest market data."""
    print(f"\n{'='*50}")
    print(f"[ANALYST] Starting AI analysis — {datetime.now()}")
    print(f"{'='*50}")

    client = get_ai_client()
    if not client:
        return None

    # Gather all latest data
    print("[ANALYST] Pulling latest data from all sources...")
    data = get_latest_data()

    # Check we have data
    total_points = sum(len(v) if isinstance(v, list) else 0 for v in data.values())
    if total_points == 0:
        print("[ERROR] No data in database. Run data fetchers first.")
        return None

    print(f"[ANALYST] Loaded {total_points} data points across {len(data)} categories.")

    # Build the prompt
    user_prompt = f"""Analyze this real-time market data and generate trading signals.

Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

=== TOP STOCK MOVERS ===
{json.dumps(data['top_movers_stocks'], indent=2)}

=== CRYPTO PRICES ===
{json.dumps(data['crypto'], indent=2)}

=== COMMODITIES ===
{json.dumps(data['commodities'], indent=2)}

=== MACRO ECONOMIC DATA ===
{json.dumps(data['macro'], indent=2)}

=== POLYMARKET PREDICTION MARKETS ===
{json.dumps(data['polymarket'], indent=2)}

=== NEWS SENTIMENT ===
{json.dumps(data['sentiment'], indent=2)}

Generate signals based on this data. Look for cross-asset patterns and mispriced Polymarket contracts."""

    # Call DeepSeek
    print("[ANALYST] Sending to DeepSeek for analysis...")

    try:
        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
        )

        raw = response.choices[0].message.content.strip()

        # Clean response — remove markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse AI response as JSON: {e}")
        print(f"[RAW RESPONSE] {raw[:500]}")
        return None
    except Exception as e:
        print(f"[ERROR] DeepSeek API call failed: {e}")
        return None

    # Display results
    print(f"\n{'='*50}")
    print(f"📊 MARKET SUMMARY")
    print(f"{'='*50}")
    print(result.get("market_summary", "No summary"))

    signals = result.get("signals", [])
    print(f"\n{'='*50}")
    print(f"🚨 SIGNALS GENERATED: {len(signals)}")
    print(f"{'='*50}")

    for i, sig in enumerate(signals, 1):
        emoji = "🟢" if sig["signal_type"] == "BUY" else "🔴" if sig["signal_type"] == "SELL" else "🟡"
        print(f"\n  {emoji} Signal #{i}: {sig['signal_type']} {sig['ticker']}")
        print(f"     Asset: {sig['asset_type']}")
        print(f"     Confidence: {sig['confidence']}%")
        print(f"     {sig['headline']}")
        print(f"     {sig['analysis'][:200]}...")

    cross = result.get("cross_asset_insights", "")
    if cross:
        print(f"\n{'='*50}")
        print(f"🔗 CROSS-ASSET INSIGHTS")
        print(f"{'='*50}")
        print(cross)

    risks = result.get("risk_warnings", "")
    if risks:
        print(f"\n{'='*50}")
        print(f"⚠️  RISK WARNINGS")
        print(f"{'='*50}")
        print(risks)

    # Save signals to DB
    save_signals(signals)

    print(f"\n[ANALYST] Analysis complete — {len(signals)} signals saved.")
    return result


def save_signals(signals):
    """Save AI-generated signals to database."""
    if not signals:
        return

    conn = get_connection()
    cursor = conn.cursor()

    for s in signals:
        cursor.execute("""
            INSERT INTO signals
            (asset_type, ticker, signal_type, confidence, headline, analysis)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            s["asset_type"], s["ticker"], s["signal_type"],
            s["confidence"], s["headline"], s["analysis"]
        ))

    conn.commit()
    conn.close()
    print(f"  [DB] Saved {len(signals)} signals.")


def get_previous_day_data():
    """Pull previous trading day's data for comparison."""
    conn = get_connection()
    cursor = conn.cursor()

    data = {}

    # Previous day stock prices
    cursor.execute("""
        SELECT ticker, asset_type, price, change_pct, volume
        FROM market_prices
        WHERE DATE(fetched_at) < DATE('now')
        ORDER BY fetched_at DESC
        LIMIT 50
    """)
    data["prev_stocks"] = [dict(r) for r in cursor.fetchall()]

    # Previous day crypto
    cursor.execute("""
        SELECT pair, price, change_pct_24h, volume_24h
        FROM crypto_prices
        WHERE DATE(fetched_at) < DATE('now')
        ORDER BY fetched_at DESC
        LIMIT 15
    """)
    data["prev_crypto"] = [dict(r) for r in cursor.fetchall()]

    # Previous day commodities
    cursor.execute("""
        SELECT name, ticker, price, change_pct
        FROM commodity_prices
        WHERE DATE(fetched_at) < DATE('now')
        ORDER BY fetched_at DESC
        LIMIT 10
    """)
    data["prev_commodities"] = [dict(r) for r in cursor.fetchall()]

    # Historical signals and their performance
    cursor.execute("""
        SELECT ticker, signal_type, confidence, headline, created_at
        FROM signals
        WHERE created_at >= datetime('now', '-7 days')
        ORDER BY created_at DESC
        LIMIT 20
    """)
    data["recent_signals"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return data


PREMARKET_PROMPT = """You are EdgeSignal AI — an elite pre-market analyst. The stock market opens in {minutes_left} minutes.

You are analyzing PREVIOUS DAY data combined with CURRENT pre-market data to generate the MOST ACCURATE opening signals possible.

CRITICAL RULES:
1. You MUST provide specific stock/asset names — no vague suggestions
2. Every signal needs: exact ticker, BUY or SELL, entry price target, stop loss, take profit
3. Confidence must be realistic — only mark 80%+ if multiple data points align
4. Compare today's pre-market data with yesterday's close to find gaps and momentum
5. Cross-reference: if crypto dumped overnight, tech stocks may open weak
6. Check macro data: if yields spiked, growth stocks face pressure
7. Polymarket probabilities can signal upcoming catalysts
8. News sentiment confirms or contradicts the price action
9. FOCUS ON ACTIONABLE TRADES — what to buy/sell at market open

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "market_summary": "3-4 sentence pre-market overview with key overnight developments",
    "market_bias": "BULLISH|BEARISH|NEUTRAL",
    "signals": [
        {{
            "asset_type": "stock|crypto|commodity|polymarket",
            "ticker": "EXACT_TICKER",
            "signal_type": "BUY|SELL",
            "confidence": 85,
            "entry_price": 150.00,
            "stop_loss": 147.00,
            "take_profit": 156.00,
            "headline": "Short punchy headline",
            "analysis": "Detailed reasoning: yesterday X closed at Y, pre-market showing Z, macro supports because...",
            "timeframe": "intraday|swing_2_5_days|position_1_4_weeks",
            "risk_reward_ratio": "1:2"
        }}
    ],
    "cross_asset_insights": "Connections between different markets affecting today's open",
    "key_levels": "Critical support/resistance levels to watch today",
    "risk_warnings": "What could invalidate these signals"
}}

Return ONLY valid JSON. No markdown, no backticks."""


def run_premarket_analysis(minute_number=1):
    """Run pre-market analysis combining previous day + current data."""
    print(f"\n[ANALYST] Running pre-market analysis (minute {minute_number}/15)...")

    client = get_ai_client()
    if not client:
        return None

    # Get current data
    current_data = get_latest_data()

    # Get previous day data for comparison
    prev_data = get_previous_day_data()

    total = sum(len(v) if isinstance(v, list) else 0 for v in current_data.values())
    total += sum(len(v) if isinstance(v, list) else 0 for v in prev_data.values())

    if total == 0:
        print("[ERROR] No data available. Run data fetchers first.")
        return None

    print(f"[ANALYST] Loaded {total} data points (current + historical).")

    minutes_left = 15 - minute_number

    user_prompt = f"""PRE-MARKET ANALYSIS — Minute {minute_number}/15 — Market opens in {minutes_left} minutes.

=== CURRENT PRE-MARKET DATA ===

TOP STOCK MOVERS (current):
{json.dumps(current_data.get('top_movers_stocks', []), indent=2)}

CRYPTO (live):
{json.dumps(current_data.get('crypto', []), indent=2)}

COMMODITIES (live):
{json.dumps(current_data.get('commodities', []), indent=2)}

MACRO DATA:
{json.dumps(current_data.get('macro', []), indent=2)}

POLYMARKET:
{json.dumps(current_data.get('polymarket', []), indent=2)}

NEWS SENTIMENT:
{json.dumps(current_data.get('sentiment', []), indent=2)}

=== PREVIOUS DAY DATA (for comparison) ===

PREVIOUS STOCKS:
{json.dumps(prev_data.get('prev_stocks', [])[:20], indent=2)}

PREVIOUS CRYPTO:
{json.dumps(prev_data.get('prev_crypto', []), indent=2)}

PREVIOUS COMMODITIES:
{json.dumps(prev_data.get('prev_commodities', []), indent=2)}

RECENT SIGNALS (last 7 days):
{json.dumps(prev_data.get('recent_signals', []), indent=2)}

Generate your most accurate pre-market signals. This is minute {minute_number} — be specific with entry, stop loss, and take profit levels."""

    try:
        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": PREMARKET_PROMPT.format(minutes_left=minutes_left)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed: {e}")
        print(f"[RAW] {raw[:500]}")
        return None
    except Exception as e:
        print(f"[ERROR] DeepSeek failed: {e}")
        return None

    # Display
    bias_icon = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}.get(result.get("market_bias", ""), "⚪")
    print(f"\n{bias_icon} Market Bias: {result.get('market_bias', 'N/A')}")
    print(f"📊 {result.get('market_summary', 'No summary')}")

    signals = result.get("signals", [])
    print(f"\n🚨 {len(signals)} signals generated:")

    for s in signals:
        icon = "🟢" if s["signal_type"] == "BUY" else "🔴"
        print(f"  {icon} [{s['signal_type']}] {s['ticker']} @ ${s.get('entry_price', 'N/A')}")
        print(f"     SL: ${s.get('stop_loss', 'N/A')} | TP: ${s.get('take_profit', 'N/A')} | Conf: {s['confidence']}%")
        print(f"     {s.get('headline', '')}")

    # Save signals
    if signals:
        save_signals(signals)

    return result


if __name__ == "__main__":
    run_analysis()
