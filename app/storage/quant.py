from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any


class QuantRunStore:
    """Persist reproducible quantitative research runs in the local SQLite DB."""

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
                    CREATE TABLE IF NOT EXISTS quant_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        generated_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        version TEXT NOT NULL,
                        config_json TEXT NOT NULL,
                        metrics_json TEXT NOT NULL,
                        result_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_quant_runs_symbol_time "
                    "ON quant_runs(symbol, generated_at DESC)"
                )
                conn.commit()
            finally:
                conn.close()

    def save(self, result: dict[str, Any]) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO quant_runs (
                        generated_at, symbol, version, config_json, metrics_json, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result["generated_at"],
                        result["symbol"],
                        result["version"],
                        json.dumps(result.get("config", {}), ensure_ascii=False, separators=(",", ":")),
                        json.dumps(result.get("metrics", {}), ensure_ascii=False, separators=(",", ":")),
                        json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()

    def recent(self, symbol: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        sql = """
            SELECT id, generated_at, symbol, version, config_json, metrics_json
            FROM quant_runs
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

        output = []
        for row in rows:
            item = dict(row)
            item["config"] = json.loads(item.pop("config_json"))
            item["metrics"] = json.loads(item.pop("metrics_json"))
            output.append(item)
        return output

    def get(self, run_id: int) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT result_json FROM quant_runs WHERE id = ?", (int(run_id),)
                ).fetchone()
            finally:
                conn.close()
        return json.loads(row["result_json"]) if row else None
