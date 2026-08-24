from app.storage.history import AnalysisHistory


def sample_payload():
    return {
        "generated_at": "2026-08-24T18:00:00+00:00",
        "symbol": "BTC-USD",
        "price": 100000.0,
        "market_decision": "COMPRAR",
        "decision": "COMPRAR",
        "execution_status": "HABILITADA",
        "confidence": 72.0,
        "institutional_score": 41.5,
        "market_regime": "TENDENCIA_ALCISTA",
        "risk": {
            "risk_percent": 1.0,
            "entry": 100000.0,
            "stop_loss": 98000.0,
            "take_profit_1": 104000.0,
            "take_profit_2": 106000.0,
        },
    }


def test_history_persists_and_filters(tmp_path):
    db = AnalysisHistory(str(tmp_path / "history.db"))
    row_id = db.save(sample_payload())
    assert row_id > 0

    rows = db.recent(symbol="btc-usd", limit=10)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC-USD"
    assert rows[0]["market_decision"] == "COMPRAR"
    assert rows[0]["entry"] == 100000.0


def test_history_empty_filter_returns_empty(tmp_path):
    db = AnalysisHistory(str(tmp_path / "history.db"))
    db.save(sample_payload())
    assert db.recent(symbol="ETH-USD", limit=10) == []
