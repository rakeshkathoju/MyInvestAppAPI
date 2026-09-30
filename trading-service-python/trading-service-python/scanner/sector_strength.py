import os
import datetime
import json
import logging
import tempfile
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BREEZE_API_KEY = os.getenv("BREEZE_API_KEY")
BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET")
BREEZE_SESSION_TOKEN = os.getenv("BREEZE_SESSION_TOKEN")
MARKET_OPEN = os.getenv("MARKET_OPEN", "09:15")
MARKET_CLOSE = os.getenv("MARKET_CLOSE", "09:30")

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
    if not all([BREEZE_API_KEY, BREEZE_API_SECRET, BREEZE_SESSION_TOKEN]):
        raise RuntimeError(
            "Missing Breeze credentials. Add BREEZE_API_KEY, BREEZE_API_SECRET, and BREEZE_SESSION_TOKEN to your .env file."
        )

    current_dir = os.getcwd()
    safe_dir = tempfile.gettempdir()
    os.makedirs(safe_dir, exist_ok=True)
    os.chdir(safe_dir)
    try:
        from breeze_connect import BreezeConnect
    finally:
        os.chdir(current_dir)

    breeze = BreezeConnect(api_key=BREEZE_API_KEY)
    breeze.generate_session(
        api_secret=BREEZE_API_SECRET,
        session_token=BREEZE_SESSION_TOKEN,
    )
    return breeze


def get_sector_performance_first_15m(breeze, sector_code):
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

    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    try:
        open_price = float(data[0]["open"])
        close_price = float(data[-1]["close"])
    except (KeyError, IndexError, ValueError) as err:
        logging.error("Error parsing Breeze response for %s: %s", sector_code, err)
        return None

    if open_price == 0:
        logging.warning("Open price is zero for %s", sector_code)
        return None

    return ((close_price - open_price) / open_price) * 100


def fetch_sector_strength():
    breeze = init_breeze_client()
    performances = {}

    for sector_name, sector_code in SECTOR_INDICES.items():
        pct_change = get_sector_performance_first_15m(breeze, sector_code)
        if pct_change is not None:
            performances[sector_name] = round(pct_change, 2)

    return performances


def build_sector_strength_json(performances):
    if not performances:
        return {
            "success": False,
            "message": "No sector performance data available.",
            "sectors": [],
            "winner": None,
            "loser": None,
        }

    sorted_perf = sorted(performances.items(), key=lambda item: item[1])
    loser, loser_pct = sorted_perf[0]
    winner, winner_pct = sorted_perf[-1]

    sector_list = [
        {"sector": sector, "performance_pct": pct}
        for sector, pct in sorted_perf
    ]

    return {
        "success": True,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "sectors": sector_list,
        "winner": {"sector": winner, "performance_pct": winner_pct},
        "loser": {"sector": loser, "performance_pct": loser_pct},
    }


def print_sector_strength_json(performances):
    output = build_sector_strength_json(performances)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    performances = fetch_sector_strength()
    print_sector_strength_json(performances)
