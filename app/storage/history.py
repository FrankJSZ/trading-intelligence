from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any


class AnalysisHistory:
    """Small local SQLite journal for analysis snapshots.

    SQLite is intentionally used here because the application is local-first and
    should not require an external database service. Writes are serialized with a
    lock so FastAPI requests cannot interleave schema/insert operations.
    """

    def __init__(self, path: str | None = None):
        configured = path or os.getenv("TI_DB_PATH") or "data/trading_intelligence.db"
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generated_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    market_decision TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    execution_status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    institutional_score REAL NOT NULL,
                    market_regime TEXT NOT NULL,
                    risk_percent REAL,
                    entry REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    payload_json TEXT NOT NULL
                )
                """
            )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_symbol_time "
                    "ON analysis_history(symbol, generated_at DESC)"
                )
                conn.commit()
            finally:
                conn.close()

    def save(self, payload: dict[str, Any]) -> int:
        risk = payload.get("risk") or {}
        row = (
            payload["generated_at"],
            payload["symbol"],
            float(payload["price"]),
            str(payload["market_decision"]),
            str(payload["decision"]),
            payload.get("execution_status", ""),
            float(payload["confidence"]),
            float(payload["institutional_score"]),
            payload.get("market_regime", ""),
            risk.get("risk_percent"),
            risk.get("entry"),
            risk.get("stop_loss"),
            risk.get("take_profit_1"),
            risk.get("take_profit_2"),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                """
                INSERT INTO analysis_history (
                    generated_at, symbol, price, market_decision, decision,
                    execution_status, confidence, institutional_score,
                    market_regime, risk_percent, entry, stop_loss,
                    take_profit_1, take_profit_2, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    row,
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()

    def recent(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        sql = """
            SELECT id, generated_at, symbol, price, market_decision, decision,
                   execution_status, confidence, institutional_score,
                   market_regime, risk_percent, entry, stop_loss,
                   take_profit_1, take_profit_2
            FROM analysis_history
        """
        params: list[Any] = []
        if symbol:
            sql += " WHERE symbol = ?"
            params.append(symbol.strip().upper())
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        return [dict(row) for row in rows]
