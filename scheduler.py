import time
from datetime import datetime
import pytz

ET = pytz.timezone("US/Eastern")


def get_et_now():
    return datetime.now(ET)


def scheduler_loop():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║            🚀 EDGESIGNAL ENGINE                          ║
║                                                          ║
║  Mode: ACTIVE                                            ║
║  Timezone: US/Eastern                                    ║
║                                                          ║
║  Stocks  ✅  Crypto    ✅  Commodities ✅               ║
║  AI Brain ✅  Telegram  ✅                               ║
╚══════════════════════════════════════════════════════════╝
    """)

    # --- Start the Telegram command bot thread ---
    from bot.commands import start_bot_thread
    start_bot_thread()

    # Main scheduling loop
    while True:
        try:
            now = get_et_now()
            print(f"\r⏳ EdgeSignal running | {now.strftime('%H:%M ET')} | Ctrl+C to stop", end="", flush=True)
            time.sleep(30)
        except KeyboardInterrupt:
            print(f"\n\n🛑 EdgeSignal stopped at {get_et_now().strftime('%H:%M:%S ET')}")
            break
        except Exception as e:
            print(f"\n[ERROR] Scheduler: {e}")
            time.sleep(60)


if __name__ == "__main__":
    scheduler_loop()