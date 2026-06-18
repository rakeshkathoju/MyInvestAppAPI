import os
import logging
from dotenv import load_dotenv
from breeze_connect import BreezeConnect

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BREEZE_API_KEY = os.getenv("BREEZE_API_KEY")
BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET")
BREEZE_SESSION_TOKEN = os.getenv("BREEZE_SESSION_TOKEN")


def init_breeze_client():
    if not all([BREEZE_API_KEY, BREEZE_API_SECRET, BREEZE_SESSION_TOKEN]):
        raise RuntimeError(
            "Missing Breeze credentials. Add BREEZE_API_KEY, BREEZE_API_SECRET, and BREEZE_SESSION_TOKEN to your .env file."
        )

    breeze = BreezeConnect(api_key=BREEZE_API_KEY)
    breeze.generate_session(api_secret=BREEZE_API_SECRET, session_token=BREEZE_SESSION_TOKEN)
    return breeze


def execute_market_order(symbol, quantity, order_type="BUY", product="CASH", exchange="NSE"):
    breeze = init_breeze_client()
    logging.info("Sending market order for %s %s", symbol, order_type)
    return breeze.place_order(
        order_type=order_type,
        tradingsymbol=symbol,
        symboltoken=symbol,
        exchange=exchange,
        quantity=quantity,
        producttype=product,
        duration="DAY",
        price=0,
        trigger_price=0
    )
