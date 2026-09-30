import os
import datetime
import time
import logging
from dotenv import load_dotenv
from breeze_connect import BreezeConnect

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BREEZE_API_KEY = os.getenv("BREEZE_API_KEY")
BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET")
BREEZE_SESSION_TOKEN = os.getenv("BREEZE_SESSION_TOKEN")
MARKET_OPEN = os.getenv("MARKET_OPEN", "09:15")
MARKET_CLOSE = os.getenv("MARKET_CLOSE", "09:30")

if not all([BREEZE_API_KEY, BREEZE_API_SECRET, BREEZE_SESSION_TOKEN]):
    raise RuntimeError(
        "Missing Breeze credentials. Set BREEZE_API_KEY, BREEZE_API_SECRET, and BREEZE_SESSION_TOKEN in your environment or .env file."
    )

SECTOR_INDICES = {
    "NIFTY IT": "NIFTYIT",
    "NIFTY BANK": "NIFTYBANK",
    "NIFTY FMCG": "NIFTYFMCG",
    "NIFTY AUTO": "NIFTYAUTO",
    "NIFTY PHARMA": "NIFTYPHARMA",
    "NIFTY ENERGY": "NIFTYENERGY",
    "NIFTY METAL": "NIFTYMETAL",
    "NIFTY REALTY": "NIFTYREALTY"
}


def init_breeze_client():
    breeze = BreezeConnect(api_key=BREEZE_API_KEY)
    breeze.generate_session(
        api_secret=BREEZE_API_SECRET,
        session_token=BREEZE_SESSION_TOKEN,
    )
    return breeze


def fetch_first_15_minute_performance(breeze, sector_code):
    today = datetime.date.today().strftime("%Y-%m-%d")
    from_date = f"{today}T{MARKET_OPEN}:00.000Z"
    to_date = f"{today}T{MARKET_CLOSE}:00.000Z"

    data = breeze.get_historical_data(
        interval="1minute",
        from_date=from_date,
        to_date=to_date,
        stock_code=sector_code,
        exchange_code="NSE",
        product_type="cash"
    )

    if not data:
        logging.warning("No data returned for %s", sector_code)
        return None

    try:
        open_price = float(data[0]["open"])
        close_price = float(data[-1]["close"])
    except (KeyError, IndexError, ValueError) as exc:
        logging.error("Failed to parse Breeze data for %s: %s", sector_code, exc)
        return None

    if open_price == 0:
        logging.warning("Open price is zero for %s", sector_code)
        return None

    return ((close_price - open_price) / open_price) * 100


def print_top_winner_loser(performers):
    if not performers:
        print("No sector performance data available.")
        return

    sorted_perf = sorted(performers.items(), key=lambda item: item[1])
    loser, loser_pct = sorted_perf[0]
    winner, winner_pct = sorted_perf[-1]

    print("\nSector performance for first 15 minutes:")
    for sector, pct in sorted_perf:
        print(f"  {sector}: {pct:.2f}%")

    print("\nTop winner:")
    print(f"  {winner}: {winner_pct:.2f}%")
    print("Top loser:")
    print(f"  {loser}: {loser_pct:.2f}%")


def run():
    breeze = init_breeze_client()
    performers = {}

    for sector_name, sector_code in SECTOR_INDICES.items():
        perf = fetch_first_15_minute_performance(breeze, sector_code)
        if perf is not None:
            performers[sector_name] = perf

    print_top_winner_loser(performers)


if __name__ == "__main__":
    run()