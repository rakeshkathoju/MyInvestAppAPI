"""Central configuration for the trading service."""
import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _num(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


# --- Database -------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Execution mode -------------------------------------------------------
# paper  -> simulated fills, no broker credentials needed
# breeze -> ICICI Direct Breeze API
# motilal-> Motilal Oswal REST API
TRADING_MODE = os.getenv("TRADING_MODE", "paper").strip().lower()

# --- Webhook security -----------------------------------------------------
# Shared secret that TradingView/Chartink alerts must send. Alerts are rejected
# when a secret is configured and the payload does not match.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# --- Risk management ------------------------------------------------------
PAPER_STARTING_CAPITAL = _num("PAPER_STARTING_CAPITAL", 1_000_000)
RISK_PER_TRADE_PCT = _num("RISK_PER_TRADE_PCT", 1.0)          # % of capital risked
MAX_POSITION_PCT = _num("MAX_POSITION_PCT", 20.0)             # % of capital per position
MAX_OPEN_POSITIONS = int(_num("MAX_OPEN_POSITIONS", 5))
DEFAULT_STOP_LOSS_PCT = _num("DEFAULT_STOP_LOSS_PCT", 0.5)
DEFAULT_TARGET_PCT = _num("DEFAULT_TARGET_PCT", 1.0)
SLIPPAGE_PCT = _num("SLIPPAGE_PCT", 0.02)
BROKERAGE_PCT = _num("BROKERAGE_PCT", 0.03)

# Reject duplicate signals for the same symbol/action within this window.
SIGNAL_DEDUPE_SECONDS = int(_num("SIGNAL_DEDUPE_SECONDS", 300))

# When false, webhooks only record signals and never place orders.
AUTO_EXECUTE = _flag("AUTO_EXECUTE", "true")

# When false, a SELL signal can only close an existing long position.
ALLOW_SHORT = _flag("ALLOW_SHORT", "false")

# Only auto-execute signals during NSE market hours when enabled.
ENFORCE_MARKET_HOURS = _flag("ENFORCE_MARKET_HOURS", "true")
MARKET_OPEN = os.getenv("MARKET_OPEN", "09:15")
MARKET_CLOSE = os.getenv("MARKET_CLOSE", "15:30")

# --- AI confirmation filter ----------------------------------------------
# When enabled, each BUY signal is sent to the AI service and only executed if
# the model agrees. Disabled by default so signals flow through untouched.
AI_CONFIRMATION_ENABLED = _flag("AI_CONFIRMATION_ENABLED", "false")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://ai-service:8000")
AI_MIN_CONFIDENCE = _num("AI_MIN_CONFIDENCE", 0.55)
AI_TIMEOUT_SECONDS = _num("AI_TIMEOUT_SECONDS", 8)
# If the AI service is unreachable, allow the trade through rather than block.
AI_FAIL_OPEN = _flag("AI_FAIL_OPEN", "true")

# --- Chartink -------------------------------------------------------------
CHARTINK_SCAN_CLAUSE = os.getenv("CHARTINK_SCAN_CLAUSE", "")
CHARTINK_POLL_SECONDS = int(_num("CHARTINK_POLL_SECONDS", 300))

# --- Breeze (ICICI Direct) ------------------------------------------------
BREEZE_API_KEY = os.getenv("BREEZE_API_KEY")
BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET")
BREEZE_SESSION_TOKEN = os.getenv("BREEZE_SESSION_TOKEN")

# --- Motilal Oswal --------------------------------------------------------
MOTILAL_API_KEY = os.getenv("MOTILAL_API_KEY")
MOTILAL_AUTH_TOKEN = os.getenv("MOTILAL_AUTH_TOKEN")
MOTILAL_CLIENT_CODE = os.getenv("MOTILAL_CLIENT_CODE")
MOTILAL_BASE_URL = os.getenv("MOTILAL_BASE_URL", "https://openapi.motilaloswal.com")
