import yfinance as yf
import json
from datetime import datetime
from core.database import get_connection
from config.assets import ALL_STOCK_TICKERS, INDEX_TICKERS


TIMEFRAMES = {
    "1m": {"period": "1d", "interval": "1m"},
    "5m": {"period": "5d", "interval": "5m"},
    "1h": {"period": "1mo", "interval": "1h"},
    "1d": {"period": "3mo", "interval": "1d"},
}


def calculate_rsi(prices, period=14):
    """Calculate RSI from a price series."""
    if len(prices) < period + 1:
        return None

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_ema(prices, period):
    """Calculate EMA from a price series."""
    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return round(ema, 4)


def calculate_macd(prices):
    """Calculate MACD (12, 26, 9)."""
    if len(prices) < 26:
        return None, None, None

    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)

    if ema12 is None or ema26 is None:
        return None, None, None

    macd_line = round(ema12 - ema26, 4)

    # Simplified signal line
    macd_values = []
    mult12 = 2 / 13
    mult26 = 2 / 27
    e12 = sum(prices[:12]) / 12
    e26 = sum(prices[:26]) / 26

    for i in range(26, len(prices)):
        e12 = (prices[i] - e12) * mult12 + e12
        e26 = (prices[i] - e26) * mult26 + e26
        macd_values.append(e12 - e26)

    if len(macd_values) >= 9:
        signal_line = round(sum(macd_values[-9:]) / 9, 4)
    else:
        signal_line = 0

    histogram = round(macd_line - signal_line, 4)

    return macd_line, signal_line, histogram


def calculate_bollinger(prices, period=20):
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        return None, None, None

    sma = sum(prices[-period:]) / period
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = variance ** 0.5

    upper = round(sma + 2 * std, 4)
    lower = round(sma - 2 * std, 4)

    return round(sma, 4), upper, lower


def calculate_vwap(highs, lows, closes, volumes):
    """Calculate VWAP."""
    if not highs or not volumes:
        return None

    typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    cumulative_tp_vol = sum(tp * v for tp, v in zip(typical_prices, volumes))
    cumulative_vol = sum(volumes)

    if cumulative_vol == 0:
        return None

    return round(cumulative_tp_vol / cumulative_vol, 4)


def analyze_ticker_multi_tf(ticker):
    """Analyze a single ticker across all timeframes."""
    result = {
        "ticker": ticker,
        "timeframes": {},
        "overall_bias": "NEUTRAL",
        "strength": 0,
    }

    scores = []

    for tf_name, tf_params in TIMEFRAMES.items():
        try:
            df = yf.download(
                ticker,
                period=tf_params["period"],
                interval=tf_params["interval"],
                progress=False,
            )

            if df.empty or len(df) < 20:
                continue

            closes = df["Close"].tolist()
            highs = df["High"].tolist()
            lows = df["Low"].tolist()
            volumes = df["Volume"].tolist()

            # Handle nested columns from yfinance
            if hasattr(closes[0], '__iter__'):
                closes = [float(c) for c in closes]
                highs = [float(h) for h in highs]
                lows = [float(l) for l in lows]
                volumes = [int(v) for v in volumes]

            latest_price = closes[-1]

            # Calculate indicators
            rsi = calculate_rsi(closes)
            ema20 = calculate_ema(closes, 20)
            ema50 = calculate_ema(closes, min(50, len(closes) - 1)) if len(closes) > 50 else None
            macd_line, macd_signal, macd_hist = calculate_macd(closes)
            bb_mid, bb_upper, bb_lower = calculate_bollinger(closes)
            vwap = calculate_vwap(highs, lows, closes, volumes)

            # Score this timeframe
            tf_score = 0
            signals = []

            # RSI
            if rsi is not None:
                if rsi < 30:
                    tf_score += 2
                    signals.append(f"RSI oversold ({rsi})")
                elif rsi > 70:
                    tf_score -= 2
                    signals.append(f"RSI overbought ({rsi})")
                elif rsi < 45:
                    tf_score += 1
                elif rsi > 55:
                    tf_score -= 1

            # EMA trend
            if ema20 and latest_price:
                if latest_price > ema20:
                    tf_score += 1
                    signals.append("Price > EMA20")
                else:
                    tf_score -= 1
                    signals.append("Price < EMA20")

            if ema50 and ema20:
                if ema20 > ema50:
                    tf_score += 1
                    signals.append("EMA20 > EMA50 (golden)")
                else:
                    tf_score -= 1
                    signals.append("EMA20 < EMA50 (death)")

            # MACD
            if macd_hist is not None:
                if macd_hist > 0:
                    tf_score += 1
                    signals.append("MACD bullish")
                else:
                    tf_score -= 1
                    signals.append("MACD bearish")

            # Bollinger Bands
            if bb_lower and bb_upper and latest_price:
                if latest_price <= bb_lower:
                    tf_score += 2
                    signals.append("At lower Bollinger Band")
                elif latest_price >= bb_upper:
                    tf_score -= 2
                    signals.append("At upper Bollinger Band")

            # VWAP (intraday only)
            if vwap and tf_name in ("1m", "5m") and latest_price:
                if latest_price > vwap:
                    tf_score += 1
                    signals.append("Above VWAP")
                else:
                    tf_score -= 1
                    signals.append("Below VWAP")

            scores.append(tf_score)

            result["timeframes"][tf_name] = {
                "price": latest_price,
                "rsi": rsi,
                "ema20": ema20,
                "ema50": ema50,
                "macd": macd_line,
                "macd_signal": macd_signal,
                "macd_histogram": macd_hist,
                "bb_upper": bb_upper,
                "bb_mid": bb_mid,
                "bb_lower": bb_lower,
                "vwap": vwap,
                "score": tf_score,
                "signals": signals,
            }

        except Exception as e:
            continue

    # Overall bias from all timeframes
    if scores:
        avg_score = sum(scores) / len(scores)
        result["strength"] = round(avg_score, 2)

        if avg_score >= 2:
            result["overall_bias"] = "STRONG_BULLISH"
        elif avg_score >= 1:
            result["overall_bias"] = "BULLISH"
        elif avg_score <= -2:
            result["overall_bias"] = "STRONG_BEARISH"
        elif avg_score <= -1:
            result["overall_bias"] = "BEARISH"
        else:
            result["overall_bias"] = "NEUTRAL"

    return result


def run_multi_timeframe_scan(tickers=None):
    """Scan multiple tickers across all timeframes."""
    if tickers is None:
        # Top 15 most active stocks + indices
        tickers = ALL_STOCK_TICKERS[:15]

    print(f"\n{'='*50}")
    print(f"[MTF] Multi-Timeframe Scan — {datetime.now()}")
    print(f"{'='*50}")
    print(f"Scanning {len(tickers)} tickers across 4 timeframes...")

    results = []
    strong_signals = []

    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}...", end=" ")

        analysis = analyze_ticker_multi_tf(ticker)
        results.append(analysis)

        bias = analysis["overall_bias"]
        strength = analysis["strength"]

        icon = {
            "STRONG_BULLISH": "🟢🟢",
            "BULLISH": "🟢",
            "NEUTRAL": "⚪",
            "BEARISH": "🔴",
            "STRONG_BEARISH": "🔴🔴",
        }.get(bias, "⚪")

        print(f"{icon} {bias} (score: {strength:+.2f})")

        # Track strong signals
        if abs(strength) >= 2:
            strong_signals.append(analysis)

        # Print timeframe details for strong signals
        if abs(strength) >= 2:
            for tf, data in analysis["timeframes"].items():
                if data.get("signals"):
                    print(f"    [{tf}] {', '.join(data['signals'][:3])}")

    # Save to database
    save_mtf_results(results)

    print(f"\n[MTF] Scan complete — {len(strong_signals)} strong signals found.")
    return results, strong_signals


def save_mtf_results(results):
    """Save multi-timeframe results to database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mtf_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            overall_bias TEXT,
            strength REAL,
            timeframe_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for r in results:
        cursor.execute("""
            INSERT INTO mtf_analysis (ticker, overall_bias, strength, timeframe_data)
            VALUES (?, ?, ?, ?)
        """, (
            r["ticker"],
            r["overall_bias"],
            r["strength"],
            json.dumps(r["timeframes"]),
        ))

    conn.commit()
    conn.close()


def get_mtf_summary_for_ai():
    """Get MTF analysis summary to feed to DeepSeek."""
    conn = get_connection()
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT ticker, overall_bias, strength, timeframe_data
        FROM mtf_analysis
        WHERE created_at = (SELECT MAX(created_at) FROM mtf_analysis)
        ORDER BY ABS(strength) DESC
    """).fetchall()

    conn.close()

    summary = []
    for r in rows:
        summary.append({
            "ticker": r["ticker"],
            "bias": r["overall_bias"],
            "strength": r["strength"],
            "details": json.loads(r["timeframe_data"]) if r["timeframe_data"] else {},
        })

    return summary


if __name__ == "__main__":
    results, strong = run_multi_timeframe_scan()
    if strong:
        print(f"\n🔥 Strong Signals:")
        for s in strong:
            print(f"  {s['ticker']}: {s['overall_bias']} ({s['strength']:+.2f})")