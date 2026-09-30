def generate_scalping_signal(latest_prices, momentum_scores):
    """Return a simple scalping signal for the current market snapshot."""
    signals = []
    for symbol, price in latest_prices.items():
        momentum = momentum_scores.get(symbol, 0)
        if momentum > 0.5:
            signals.append({"symbol": symbol, "action": "buy", "price": price})
        elif momentum < -0.5:
            signals.append({"symbol": symbol, "action": "sell", "price": price})
    return signals
