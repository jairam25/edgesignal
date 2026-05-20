import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME = "EdgeSignal"
    VERSION = "0.1.0"
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    BASE_DIR = BASE_DIR

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = "deepseek-chat"

    ALIBABA_API_KEY = os.getenv("ALIBABA_API_KEY", "")
    ALIBABA_BASE_URL = os.getenv("ALIBABA_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    ALIBABA_MODEL = "qwen-plus"

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

    ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
    FRED_API_KEY = os.getenv("FRED_API_KEY", "")
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "edgesignal:v1.0")

    POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://clob.polymarket.com")

    DB_PATH = BASE_DIR / "data" / "edgesignal.db"
    DB_URL = f"sqlite:///{DB_PATH}"

    STOCK_REFRESH_INTERVAL = 300
    CRYPTO_REFRESH_INTERVAL = 120
    COMMODITY_REFRESH_INTERVAL = 600
    POLYMARKET_REFRESH_INTERVAL = 180
    NEWS_REFRESH_INTERVAL = 300
    ANALYSIS_INTERVAL = 600

    SIGNAL_CONFIDENCE_THRESHOLD = int(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", "70"))
    POLYMARKET_EDGE_THRESHOLD = 15

    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_DIR = BASE_DIR / "logs"

    @classmethod
    def validate(cls):
        missing = []
        if not cls.DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")
        if missing:
            print(f"[WARNING] Missing config: {', '.join(missing)}")
            print("Some features will be unavailable.")
        return len(missing) == 0


settings = Settings()