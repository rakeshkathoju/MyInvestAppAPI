"""
MyInvestApp MCP Server
----------------------
Exposes the MyInvestApp API as MCP tools so AI assistants (GitHub Copilot,
Claude, Cursor, etc.) can query and interact with the trading platform.

Tools:
  check_health          — Check all service statuses
  get_stocks            — List all stock signals from the trading service
  place_trade           — Record a new trade / stock signal
  get_ai_prediction     — Get BUY / SELL / HOLD signal for a ticker
  train_ai_model        — Retrain the AI model on fresh market data
  get_user              — Fetch a user's profile
  get_user_portfolio    — Fetch a user's portfolio

Transport:
  - stdio  (default) — for VS Code Copilot / local AI assistants
  - sse               — set MCP_TRANSPORT=sse for HTTP deployment (port 8002)
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:3000").rstrip("/")
MCP_TRANSPORT   = os.getenv("MCP_TRANSPORT", "stdio")   # "stdio" | "sse"
MCP_PORT        = int(os.getenv("MCP_PORT", "8002"))

mcp = FastMCP(
    name="MyInvestApp",
    instructions=(
        "You have access to the MyInvestApp trading platform. "
        "Use these tools to query stock signals, get AI predictions, manage trades, "
        "and check service health. "
        "For stock tickers, use NSE format e.g. 'ICICIBANK.NS', 'RELIANCE.NS'."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(path: str, timeout: float = 10.0) -> dict:
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(f"{API_GATEWAY_URL}{path}")
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: dict, timeout: float = 30.0) -> dict:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{API_GATEWAY_URL}{path}", json=body)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_health() -> dict:
    """
    Check the health and connectivity status of all MyInvestApp services
    (API Gateway, Trading Service, AI Service, User Service).
    Returns each service's status.
    """
    return _get("/health")


@mcp.tool()
def get_stocks() -> list:
    """
    Get all stock signals stored in the trading database.
    Returns a list of signals with stock name, price, target, stop loss,
    quantity, risk/reward ratio, and P&L.
    """
    result = _get("/stocks")
    return result if isinstance(result, list) else [result]


@mcp.tool()
def place_trade(
    stock_name: str,
    price: float,
    target: float,
    stop_loss: float,
    quantity: int,
    risk_reward: float = 0.0,
    pnl: float = 0.0,
) -> dict:
    """
    Record a new trade or stock signal in the trading database.

    Args:
        stock_name:   Stock ticker or name (e.g. "ICICIBANK", "RELIANCE")
        price:        Entry price
        target:       Target / take-profit price
        stop_loss:    Stop-loss price
        quantity:     Number of shares / lots
        risk_reward:  Risk-reward ratio (optional, computed if 0)
        pnl:          Realised P&L (optional, 0 for open trades)
    """
    if risk_reward == 0.0 and price > 0 and price != stop_loss:
        risk_reward = round((target - price) / (price - stop_loss), 2)

    return _post("/trade", {
        "stock_name":   stock_name,
        "price":        price,
        "target":       target,
        "stop_loss":    stop_loss,
        "quantity":     quantity,
        "risk_reward":  risk_reward,
        "pnl":          pnl,
    })


@mcp.tool()
def get_ai_prediction(ticker: str = "ICICIBANK.NS") -> dict:
    """
    Get an AI-generated BUY / SELL / HOLD signal for a stock ticker.
    The model uses technical indicators (VWAP gap, EMA ratio, RSI, ATR,
    volume ratio, momentum) trained on 1-minute candle data.

    Args:
        ticker: Yahoo Finance ticker symbol (e.g. "ICICIBANK.NS", "RELIANCE.NS")

    Returns:
        signal (BUY/SELL/HOLD), buy_probability, and the ticker used.
    """
    return _post("/ai/predict", {"ticker": ticker}, timeout=20.0)


@mcp.tool()
def train_ai_model(ticker: str = "ICICIBANK.NS", days: int = 7) -> dict:
    """
    Retrain the AI prediction model on fresh 1-minute market data.
    Downloads the latest data from Yahoo Finance and fits a Random Forest
    classifier. Returns accuracy and precision metrics.

    Args:
        ticker: Yahoo Finance ticker symbol (e.g. "ICICIBANK.NS")
        days:   Number of past days of 1-min data to train on (max ~7 due to
                Yahoo Finance limitations for 1-min interval)
    """
    return _post("/ai/train", {"ticker": ticker, "days": days}, timeout=180.0)


@mcp.tool()
def get_user(user_id: int) -> dict:
    """
    Fetch a user's profile by their ID.

    Args:
        user_id: The user's numeric ID
    """
    return _get(f"/users/{user_id}")


@mcp.tool()
def get_user_portfolio(user_id: int) -> dict:
    """
    Fetch a user's investment portfolio by their ID.
    Returns the holdings and any portfolio summary data.

    Args:
        user_id: The user's numeric ID
    """
    return _get(f"/users/{user_id}/portfolio")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if MCP_TRANSPORT == "sse":
        mcp.run(transport="sse", port=MCP_PORT)
    else:
        mcp.run(transport="stdio")
