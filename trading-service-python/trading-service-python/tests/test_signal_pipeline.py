"""End-to-end tests for the signal -> paper trade pipeline.

Run with:  pytest trading-service-python/tests -q
Market data is stubbed so the suite never touches the network or a database.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import execution  # noqa: E402
import market_data  # noqa: E402
from engine import signal_store, trade_engine  # noqa: E402
from signals import chartink, tradingview  # noqa: E402
from signals.models import Signal, SignalError, normalize_symbol  # noqa: E402

PRICES = {"RELIANCE": 1000.0, "SBIN": 500.0, "TATAMOTORS": 400.0, "INFY": 1500.0}


@pytest.fixture(autouse=True)
def isolated_engine(monkeypatch):
    """Fresh paper broker, deterministic prices, no market-hour gate."""
    monkeypatch.setattr(market_data, "get_ltp", lambda s, e="NSE": PRICES.get(s))
    monkeypatch.setattr(config, "ENFORCE_MARKET_HOURS", False)
    monkeypatch.setattr(config, "AI_CONFIRMATION_ENABLED", False)
    monkeypatch.setattr(config, "SLIPPAGE_PCT", 0.0)
    monkeypatch.setattr(config, "BROKERAGE_PCT", 0.0)
    monkeypatch.setattr(config, "TRADING_MODE", "paper")

    execution.reset_cache()
    signal_store.clear_dedupe_cache()
    execution.get_paper_broker().reset()
    yield
    execution.reset_cache()


def buy(symbol, **kwargs):
    return Signal.build("test", {"symbol": symbol, "action": "BUY", **kwargs})


# --- parsing --------------------------------------------------------------
def test_normalizes_tradingview_symbol_formats():
    assert normalize_symbol("NSE:RELIANCE") == "RELIANCE"
    assert normalize_symbol("reliance.ns") == "RELIANCE"
    assert normalize_symbol("SBIN-EQ") == "SBIN"


def test_tradingview_json_alert():
    signals = tradingview.parse(
        {"symbol": "NSE:RELIANCE", "action": "buy", "price": "1000", "stop_loss": "990"}
    )
    assert len(signals) == 1
    assert (signals[0].symbol, signals[0].action, signals[0].stop_loss) == ("RELIANCE", "BUY", 990.0)


def test_tradingview_plain_text_alert():
    signal = tradingview.parse("SELL SBIN 505.5")[0]
    assert (signal.symbol, signal.action, signal.price) == ("SBIN", "SELL", 505.5)


def test_tradingview_ignores_unsubstituted_placeholders():
    signal = tradingview.parse({"symbol": "SBIN", "action": "buy", "price": "{{close}}"})[0]
    assert signal.price is None


def test_chartink_alert_fans_out_to_one_signal_per_stock():
    signals = chartink.parse(
        {
            "stocks": "SBIN,TATAMOTORS",
            "trigger_prices": "500,400",
            "scan_name": "Breakout",
            "alert_name": "Intraday",
        }
    )
    assert [s.symbol for s in signals] == ["SBIN", "TATAMOTORS"]
    assert [s.price for s in signals] == [500.0, 400.0]
    assert all(s.action == "BUY" and s.strategy == "Breakout" for s in signals)


def test_rejects_unknown_action():
    with pytest.raises(SignalError):
        Signal.build("test", {"symbol": "SBIN", "action": "hodl"})


# --- paper fills ----------------------------------------------------------
def test_buy_opens_position_and_sell_closes_it_with_pnl():
    trade_engine.process_now(buy("RELIANCE", price=1000, quantity=10))

    broker = execution.get_paper_broker()
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0]["quantity"] == 10
    assert positions[0]["side"] == "LONG"

    exit_signal = Signal.build("test", {"symbol": "RELIANCE", "action": "SELL", "price": 1100})
    trade_engine.process_now(exit_signal)

    assert broker.get_positions() == []
    assert broker.get_pnl()["realized_pnl"] == pytest.approx(1000.0)


def test_averaging_up_updates_average_price():
    trade_engine.process_now(buy("SBIN", price=500, quantity=10))
    trade_engine.process_now(buy("SBIN", price=600, quantity=10))

    position = execution.get_paper_broker().get_positions()[0]
    assert position["quantity"] == 20
    assert position["avg_price"] == pytest.approx(550.0)


def test_sell_without_position_is_rejected_when_shorting_disabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_SHORT", False)
    result = trade_engine.process_now(
        Signal.build("test", {"symbol": "INFY", "action": "SELL", "price": 1500})
    )
    assert result["status"] == "rejected"
    assert "shorting is disabled" in result["reason"]


def test_sell_exits_only_the_held_quantity():
    trade_engine.process_now(buy("INFY", price=1500, quantity=5))
    # Signal carries no quantity - the engine must square off exactly what is held.
    trade_engine.process_now(
        Signal.build("test", {"symbol": "INFY", "action": "SELL", "price": 1600})
    )
    broker = execution.get_paper_broker()
    assert broker.get_positions() == []
    assert broker.get_pnl()["realized_pnl"] == pytest.approx(500.0)


# --- risk engine ----------------------------------------------------------
def test_position_is_sized_from_risk_budget(monkeypatch):
    monkeypatch.setattr(config, "RISK_PER_TRADE_PCT", 1.0)
    monkeypatch.setattr(config, "MAX_POSITION_PCT", 100.0)

    # Risking 10 per share with a 10,000 budget => 1000 shares.
    trade_engine.process_now(buy("RELIANCE", price=1000, stop_loss=990))
    assert execution.get_paper_broker().get_positions()[0]["quantity"] == 1000


def test_exposure_cap_limits_size(monkeypatch):
    monkeypatch.setattr(config, "MAX_POSITION_PCT", 1.0)
    trade_engine.process_now(buy("RELIANCE", price=1000, stop_loss=999))
    assert execution.get_paper_broker().get_positions()[0]["quantity"] == 10


def test_default_stop_and_target_are_applied(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_STOP_LOSS_PCT", 1.0)
    monkeypatch.setattr(config, "DEFAULT_TARGET_PCT", 2.0)

    trade_engine.process_now(buy("RELIANCE", price=1000, quantity=1))
    position = execution.get_paper_broker().get_positions()[0]
    assert position["stop_loss"] == pytest.approx(990.0)
    assert position["target"] == pytest.approx(1020.0)


def test_max_open_positions_is_enforced(monkeypatch):
    monkeypatch.setattr(config, "MAX_OPEN_POSITIONS", 1)
    trade_engine.process_now(buy("RELIANCE", price=1000, quantity=1))
    result = trade_engine.process_now(buy("SBIN", price=500, quantity=1))

    assert result["status"] == "rejected"
    assert "Max open positions" in result["reason"]


def test_market_closed_blocks_execution(monkeypatch):
    monkeypatch.setattr(trade_engine.risk, "is_market_open", lambda: False)
    result = trade_engine.process_now(buy("RELIANCE", price=1000, quantity=1))
    assert result["status"] == "rejected"
    assert result["reason"] == "Market is closed"


# --- dedupe & AI filter ---------------------------------------------------
def test_duplicate_signals_are_skipped(monkeypatch):
    monkeypatch.setattr(config, "SIGNAL_DEDUPE_SECONDS", 300)
    first = trade_engine.submit([buy("SBIN", price=500, quantity=1)], execute=False)
    second = trade_engine.submit([buy("SBIN", price=500, quantity=1)], execute=False)

    assert first["queued"] == 1
    assert second["queued"] == 0
    assert second["rejected"][0]["reason"] == "duplicate"


def test_ai_filter_can_block_a_buy(monkeypatch):
    monkeypatch.setattr(config, "AI_CONFIRMATION_ENABLED", True)
    monkeypatch.setattr(
        trade_engine.ai_filter, "confirm", lambda s: (False, "AI filter rejected SBIN")
    )
    result = trade_engine.process_now(buy("SBIN", price=500, quantity=1))
    assert result["status"] == "rejected"
    assert "AI filter rejected" in result["reason"]


def test_ai_filter_never_blocks_an_exit(monkeypatch):
    trade_engine.process_now(buy("SBIN", price=500, quantity=2))
    monkeypatch.setattr(config, "AI_CONFIRMATION_ENABLED", True)
    monkeypatch.setattr(trade_engine.ai_filter, "confirm", lambda s: (False, "blocked"))

    trade_engine.process_now(
        Signal.build("test", {"symbol": "SBIN", "action": "SELL", "price": 520})
    )
    assert execution.get_paper_broker().get_positions() == []


# --- broker switching -----------------------------------------------------
def test_trading_mode_selects_the_broker(monkeypatch):
    assert execution.get_broker().name == "paper"

    execution.reset_cache()
    monkeypatch.setattr(config, "TRADING_MODE", "icicidirect")
    assert execution.get_broker().name == "breeze"

    execution.reset_cache()
    monkeypatch.setattr(config, "TRADING_MODE", "motilal")
    assert execution.get_broker().name == "motilal"


def test_unknown_mode_falls_back_to_paper(monkeypatch):
    execution.reset_cache()
    monkeypatch.setattr(config, "TRADING_MODE", "zerodha")
    assert execution.get_broker().name == "paper"
