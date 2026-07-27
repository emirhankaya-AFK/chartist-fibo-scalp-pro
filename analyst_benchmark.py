"""Import and normalize the external analyst alarm history.

The alarm database is treated as an observation log only.  A level alert is
not converted into a buy/sell signal and no return is invented when the
source did not record an entry price and an exit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


NODE_DB = Path(r"C:\Users\emirh\.gemini\antigravity\scratch\investing-stock-alarm\data\db.json")


def _source(text: str) -> str:
    m = re.match(r"\s*\[([^\]]+)\]", text or "")
    return m.group(1).strip() if m else "Bilinmiyor"


def _role(text: str, alarm_type: str) -> str:
    t = (text or "").lower()
    if any(x in t for x in ("satış", "sat", "direnç", "kâr", "kar al", "hedef")):
        return "kâr alma / direnç"
    if "destek" in t and "stop" in t:
        return "destek / stop"
    if "alım" in t:
        return "alım bölgesi"
    if any(x in t for x in ("stop", "zarar", "risk")):
        return "stop / risk"
    if any(x in t for x in ("destek", "dip")):
        return "alım / destek"
    return "üst seviye" if alarm_type == "above" else "alt seviye"


def _normalize(item: dict[str, Any], status: str) -> dict[str, Any]:
    description = str(item.get("description") or "")
    symbol = str(item.get("symbol") or "").upper().removesuffix(".IS")
    target = item.get("targetValue")
    triggered = item.get("triggerValue")
    entry = item.get("purchasePrice")
    observed_return = None
    try:
        if entry is not None and triggered is not None and float(entry) > 0:
            observed_return = round((float(triggered) / float(entry) - 1) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        observed_return = None
    return {
        "id": item.get("id"), "ticker": symbol,
        "source": _source(description), "role": _role(description, str(item.get("type") or "")),
        "type": item.get("type"), "level": target, "triggerValue": triggered,
        "status": status, "description": description,
        "timestamp": item.get("timestamp") or item.get("createdAt"),
        "entry": entry,
        "observedReturn": observed_return,
        "realizedReturn": None,
        "returnStatus": "tetiklenme anı brüt değişim" if observed_return is not None else "giriş fiyatı kaydedilmemiş",
    }


def load_analyst_alerts(limit: int = 500) -> dict[str, Any]:
    if not NODE_DB.exists():
        return {"status": "unavailable", "message": "Alarm veritabanı bulunamadı", "alerts": [], "history": [], "summary": {}}
    try:
        raw = json.loads(NODE_DB.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "message": f"Alarm geçmişi okunamadı: {exc}", "alerts": [], "history": [], "summary": {}}
    active = [_normalize(x, "active" if x.get("active", True) else "inactive") for x in (raw.get("alerts") or [])]
    history = [_normalize(x, "triggered") for x in (raw.get("history") or [])]
    alerts = (active + history)[: max(1, min(limit, 2000))]
    by_source: dict[str, int] = {}
    for row in alerts:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    return {"status": "ok", "source": str(NODE_DB), "alerts": alerts, "history": history,
            "summary": {"active": len(active), "triggered": len(history), "total": len(alerts), "bySource": by_source,
                        "returnsAvailable": 0,
                        "observedReturnsAvailable": sum(x.get("observedReturn") is not None for x in history)}}
