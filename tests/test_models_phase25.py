from app.models import WatchlistRequest


def test_watchlist_normalizes_and_deduplicates_symbols():
    req = WatchlistRequest(symbols=[" btc-usd ", "BTC-USD", "nvda"])
    assert req.symbols == ["BTC-USD", "NVDA"]
