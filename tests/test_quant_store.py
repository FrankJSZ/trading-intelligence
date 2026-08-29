from app.storage.quant import QuantRunStore


def sample_result():
    return {
        "generated_at": "2026-08-29T12:00:00+00:00",
        "symbol": "BTC-USD",
        "version": "quant-core-v1",
        "config": {"capital": 10000, "risk_percent": 1.0},
        "metrics": {"trades": 42, "expectancy_r": 0.31},
        "trades": [],
    }


def test_quant_store_round_trip(tmp_path):
    store = QuantRunStore(str(tmp_path / "quant.db"))
    run_id = store.save(sample_result())
    assert run_id > 0

    recent = store.recent(symbol="btc-usd", limit=5)
    assert len(recent) == 1
    assert recent[0]["symbol"] == "BTC-USD"
    assert recent[0]["metrics"]["trades"] == 42

    full = store.get(run_id)
    assert full is not None
    assert full["version"] == "quant-core-v1"
    assert full["config"]["risk_percent"] == 1.0
