"""Cloud-friendly paper trading core. No broker or real-order integration."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("DEMO_DB_PATH", str(Path(__file__).resolve().parent / "data" / "demo_trading.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.RLock()
_initialized = False


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=2)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=1500")
    return db


def init_db() -> None:
    global _initialized
    if _initialized:
        return
    with _lock, closing(_connect()) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          initial_balance REAL NOT NULL,
          bist_budget REAL NOT NULL,
          us_budget REAL NOT NULL,
          crypto_budget REAL NOT NULL,
          crypto_margin_limit REAL NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trades (
          id TEXT PRIMARY KEY,
          symbol TEXT NOT NULL,
          market TEXT NOT NULL,
          side TEXT NOT NULL,
          status TEXT NOT NULL,
          entry_price REAL NOT NULL,
          exit_price REAL,
          margin_usd REAL NOT NULL,
          leverage REAL NOT NULL,
          notional_usd REAL NOT NULL,
          tp1 REAL,
          tp2 REAL,
          stop_loss REAL,
          pnl_usd REAL,
          reasoning TEXT NOT NULL,
          worker TEXT,
          worker_response TEXT,
          opened_at TEXT NOT NULL,
          closed_at TEXT,
          close_reason TEXT
        );
        """)
        if db.execute("SELECT 1 FROM portfolio WHERE id=1").fetchone() is None:
            db.execute("INSERT INTO portfolio VALUES (1,3500,1000,1000,1000,500,?)", (_now(),))
        db.commit()
        _initialized = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def portfolio() -> dict:
    if not _initialized:
        init_db()
    with closing(_connect()) as db:
        p = dict(db.execute("SELECT * FROM portfolio WHERE id=1").fetchone())
        rows = [dict(r) for r in db.execute("SELECT * FROM trades ORDER BY opened_at DESC").fetchall()]
    realized = sum(float(r.get("pnl_usd") or 0) for r in rows if r["status"] == "closed")
    return {"mode": "demo", "real_orders": False, "portfolio": p, "realized_pnl_usd": realized, "trades": rows}


def open_trade(data: dict) -> dict:
    if not _initialized:
        init_db()
    market = str(data.get("market", "")).lower().strip()
    symbol = str(data.get("symbol", "")).strip().upper()
    side = str(data.get("side", "")).lower().strip()
    if market not in {"bist", "us", "crypto"}:
        raise ValueError("market bist, us veya crypto olmalı")
    if not symbol or side not in {"long", "short"}:
        raise ValueError("symbol ve side (long/short) gerekli")
    entry = float(data.get("entry_price", 0))
    margin = float(data.get("margin_usd", 0))
    leverage = float(data.get("leverage", 1))
    if entry <= 0 or margin <= 0:
        raise ValueError("entry_price ve margin_usd pozitif olmalı")
    if market != "crypto" and leverage != 1:
        raise ValueError("BIST ve ABD işlemlerinde kaldıraç kullanılamaz")
    if market == "crypto" and (leverage < 1 or leverage > 55):
        raise ValueError("Kripto kaldıraç 1 ile 55 arasında olmalı")
    if market == "crypto" and margin > 500:
        raise ValueError("Kripto teminatı 500 USD sınırını aşamaz")
    reasoning = str(data.get("reasoning", "Kullanıcı komutu ile açılan demo işlem")).strip()
    now = _now()
    row = {
        "id": str(uuid.uuid4()), "symbol": symbol, "market": market, "side": side,
        "status": "open", "entry_price": entry, "exit_price": None,
        "margin_usd": margin, "leverage": leverage, "notional_usd": margin * leverage,
        "tp1": data.get("tp1"), "tp2": data.get("tp2"), "stop_loss": data.get("stop_loss"),
        "pnl_usd": None, "reasoning": reasoning, "worker": data.get("worker"),
        "worker_response": data.get("worker_response"), "opened_at": now,
        "closed_at": None, "close_reason": None,
    }
    with _lock, closing(_connect()) as db:
        db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
        db.commit()
    return row


def close_trade(trade_id: str, exit_price: float, reason: str = "manual") -> dict:
    if not _initialized:
        init_db()
    if exit_price <= 0:
        raise ValueError("exit_price pozitif olmalı")
    with _lock, closing(_connect()) as db:
        trade = db.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if trade is None:
            raise ValueError("işlem bulunamadı")
        if trade["status"] != "open":
            raise ValueError("işlem zaten kapalı")
        direction = 1 if trade["side"] == "long" else -1
        pnl = direction * ((exit_price - trade["entry_price"]) / trade["entry_price"]) * trade["notional_usd"]
        db.execute("UPDATE trades SET status='closed', exit_price=?, pnl_usd=?, closed_at=?, close_reason=? WHERE id=?", (exit_price, pnl, _now(), reason, trade_id))
        result = dict(db.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone())
        db.commit()
    return result

