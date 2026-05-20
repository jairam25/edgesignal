import requests
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from core.database import get_connection
from config.assets import ALL_STOCK_TICKERS


# Free RSS news feeds — no API key needed
RSS_FEEDS = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "investing": "https://www.investing.com/rss/news.rss",
}

BULLISH_WORDS = [
    "buy", "bullish", "surge", "rally", "gain", "rise", "jump",
    "soar", "breakout", "upgrade", "beat", "record", "high",
    "growth", "profit", "boom", "strong", "upside", "momentum",
]

BEARISH_WORDS = [
    "sell", "bearish", "crash", "drop", "fall", "decline", "plunge",
    "tank", "dump", "downgrade", "miss", "low", "loss", "weak",
    "fear", "risk", "recession", "inflation", "cut", "warning",
]

CRYPTO_NAMES = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "solana": "SOL", "dogecoin": "DOGE", "doge": "DOGE",
    "xrp": "XRP", "ripple": "XRP", "cardano": "ADA",
    "avalanche": "AVAX", "polkadot": "DOT",
    "chainlink": "LINK", "litecoin": "LTC",
    "crypto": "CRYPTO", "cryptocurrency": "CRYPTO",
}


def score_text(text):
    """Score text as bullish (+) or bearish (-)."""
    text_lower = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bear = sum(1 for w in BEARISH_WORDS if w in text_lower)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 4)


def find_tickers_in_text(text):
    """Find mentioned tickers in text."""
    found = []

    for ticker in ALL_STOCK_TICKERS:
        if len(ticker) < 3:
            continue
        if re.search(r'\b' + re.escape(ticker) + r'\b', text):
            found.append(ticker)

    text_lower = text.lower()
    for name, symbol in CRYPTO_NAMES.items():
        if name in text_lower:
            found.append(symbol)

    return list(set(found))


def fetch_rss(url):
    """Fetch and parse an RSS feed."""
    try:
        response = requests.get(url, timeout=15, headers={
            "User-Agent": "EdgeSignal/1.0"
        })
        response.raise_for_status()
        root = ET.fromstring(response.content)

        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            desc = item.findtext("description", "")
            items.append(f"{title} {desc}")

        return items

    except Exception as e:
        return []


def fetch_sentiment():
    """Fetch news headlines and calculate sentiment per ticker."""
    print(f"\n[SENTIMENT] Scanning {len(RSS_FEEDS)} news feeds...")

    ticker_data = defaultdict(lambda: {"scores": [], "count": 0})
    total_articles = 0

    for feed_name, url in RSS_FEEDS.items():
        articles = fetch_rss(url)
        matched = 0

        for text in articles:
            tickers = find_tickers_in_text(text)
            if not tickers:
                continue

            score = score_text(text)
            for ticker in tickers:
                ticker_data[ticker]["scores"].append(score)
                ticker_data[ticker]["count"] += 1

            matched += 1

        total_articles += len(articles)
        print(f"  {feed_name}: {len(articles)} articles, {matched} had tickers")

    # Calculate average sentiment
    results = []
    for ticker, data in ticker_data.items():
        if data["scores"]:
            avg_score = round(sum(data["scores"]) / len(data["scores"]), 4)
        else:
            avg_score = 0.0

        sentiment = "BULLISH" if avg_score > 0.1 else "BEARISH" if avg_score < -0.1 else "NEUTRAL"

        results.append({
            "ticker": ticker,
            "source": "news",
            "score": avg_score,
            "post_count": data["count"],
            "summary": sentiment,
        })

    results.sort(key=lambda x: x["post_count"], reverse=True)

    print(f"\n  Top mentioned tickers:")
    for r in results[:15]:
        bar = "🟢" if r["score"] > 0.1 else "🔴" if r["score"] < -0.1 else "⚪"
        print(f"    {bar} {r['ticker']}: {r['summary']} ({r['score']:+.2f}) — {r['post_count']} mentions")

    if results:
        save_sentiment(results)

    print(f"\n[SENTIMENT] Done — {len(results)} tickers tracked from {total_articles} articles.")
    return results


def save_sentiment(records):
    """Save sentiment data to database."""
    conn = get_connection()
    cursor = conn.cursor()

    for r in records:
        cursor.execute("""
            INSERT INTO sentiment
            (ticker, source, score, post_count, summary)
            VALUES (?, ?, ?, ?, ?)
        """, (
            r["ticker"], r["source"], r["score"],
            r["post_count"], r["summary"]
        ))

    conn.commit()
    conn.close()
    print(f"  [DB] Saved {len(records)} sentiment records.")


if __name__ == "__main__":
    fetch_sentiment()