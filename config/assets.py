SP500_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "TSLA",
    "UNH", "XOM", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "AVGO", "COST", "WMT", "MCD", "CSCO",
    "ACN", "CRM", "AMD"
]

DJIA_TICKERS = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
    "DOW", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WMT",
    "NVDA"
]

NASDAQ_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA",
    "AVGO", "COST", "PEP", "CSCO", "AMD", "ADBE", "NFLX", "INTC",
    "CMCSA", "QCOM", "TXN", "INTU"
]

ETF_TICKERS = [
    "SPY", "QQQ", "DIA", "IWM", "VTI",
    "XLE", "XLF", "XLK", "XLV", "XLI",
    "GLD", "SLV", "USO", "UNG",
    "TLT", "HYG", "LQD",
    "EEM", "VWO", "EFA",
    "ARKK", "ARKW",
]

COMMODITY_TICKERS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Crude Oil WTI": "CL=F",
    "Brent Crude": "BZ=F",
    "Natural Gas": "NG=F",
    "Copper": "HG=F",
    "Wheat": "ZW=F",
    "Corn": "ZC=F",
    "Soybeans": "ZS=F",
    "Platinum": "PL=F",
}

CRYPTO_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "DOT/USDT", "POL/USDT",
    "LINK/USDT", "UNI/USDT", "ATOM/USDT", "LTC/USDT", "APT/USDT",
]

FRED_SERIES = {
    "Federal Funds Rate": "FEDFUNDS",
    "10Y Treasury Yield": "DGS10",
    "2Y Treasury Yield": "DGS2",
    "CPI (YoY)": "CPIAUCSL",
    "Unemployment Rate": "UNRATE",
    "GDP Growth": "A191RL1Q225SBEA",
    "M2 Money Supply": "M2SL",
    "Dollar Index": "DTWEXBGS",
}

INDEX_TICKERS = {
    "S&P 500": "^GSPC",
    "DJIA": "^DJI",
    "NASDAQ Composite": "^IXIC",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
}

ALL_STOCK_TICKERS = list(set(
    SP500_TICKERS + DJIA_TICKERS + NASDAQ_TICKERS
))

ALL_WATCHLIST = {
    "stocks": ALL_STOCK_TICKERS,
    "etfs": ETF_TICKERS,
    "commodities": COMMODITY_TICKERS,
    "crypto": CRYPTO_PAIRS,
    "indices": INDEX_TICKERS,
    "macro": FRED_SERIES,
}