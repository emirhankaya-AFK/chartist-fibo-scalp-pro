"""15-minute delayed opportunity poller.

It never places orders. Notifications are opt-in via NTFY_TOPIC and NTFY_TOKEN.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from datetime import datetime
from threading import Lock

from market_scanner import scan_market


INTERVAL_SECONDS = int(os.getenv("OPPORTUNITY_INTERVAL_SECONDS", "900"))
STATE_PATH = Path(__file__).with_name("intraday_alert_state.json")
NOTIFICATION_LOG_PATH = Path(__file__).with_name("notification_log.json")
TRACKING_LOG_PATH = Path(__file__).with_name("tracking_log.json")
MANUAL_TRACKING_PATH = Path(__file__).with_name("manual_tracking.json")
DEFAULT_NTFY_TOPIC = "emirkan_bist_alarm"
_status_lock = Lock()
_status = {
    "running": False,
    "lastRun": None,
    "lastError": None,
    "opportunities": [],
    "tracking": [],
    "notificationsEnabled": True,
    "topic": os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip(),
}

def _load_state() -> dict[str, str]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_state(state: dict[str, str]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def manual_tracking() -> list[str]:
    try:
        rows = json.loads(MANUAL_TRACKING_PATH.read_text(encoding="utf-8")) if MANUAL_TRACKING_PATH.exists() else []
        return [str(item).upper().replace(".IS", "") for item in rows if str(item).strip()] if isinstance(rows, list) else []
    except (OSError, ValueError, TypeError):
        return []


def add_manual_tracking(ticker: str) -> list[str]:
    ticker = str(ticker).upper().replace(".IS", "").strip()
    rows = manual_tracking()
    if ticker and ticker not in rows:
        rows.append(ticker)
        MANUAL_TRACKING_PATH.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def _append_notification_log(item: dict, message: str, delivered: bool) -> None:
    try:
        rows = json.loads(NOTIFICATION_LOG_PATH.read_text(encoding="utf-8")) if NOTIFICATION_LOG_PATH.exists() else []
        if not isinstance(rows, list):
            rows = []
        if not delivered:
            for previous in rows:
                if previous.get("ticker") == item.get("ticker") and previous.get("status") == "not_sent":
                    previous["timestamp"] = datetime.now().astimezone().isoformat(timespec="seconds")
                    previous["message"] = message
                    previous["attempts"] = int(previous.get("attempts", 1)) + 1
                    NOTIFICATION_LOG_PATH.write_text(json.dumps(rows[:500], ensure_ascii=False), encoding="utf-8")
                    return
        rows.insert(0, {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "ticker": item.get("ticker"),
            "price": item.get("price"),
            "strategy": item.get("strategy"),
            "score": item.get("score"),
            "message": message,
            "status": "sent" if delivered else "not_sent",
            "reason": "ntfy gönderimi başarısız veya NTFY_TOPIC eksik" if not delivered else "",
            "attempts": 1,
        })
        NOTIFICATION_LOG_PATH.write_text(json.dumps(rows[:500], ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass


def _notify(message: str) -> bool:
    topic = os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()
    if not topic:
        return False
    url = f"https://ntfy.sh/{topic}"
    headers = {"Title": "Chartist Fibo-Scalp Pro", "Priority": "high", "Tags": "chart_with_upwards_trend,bell"}
    token = os.getenv("NTFY_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15):
            return True
    except Exception:
        return False


def _append_trade_event(track: dict, event_type: str, price: float, now: str) -> None:
    """Store one lifecycle event per ticker/event type, and optionally push it once."""
    seen = set(track.setdefault("eventTypes", []))
    if event_type in seen:
        return
    entry = float(track.get("startPrice") or price)
    high = float(track.get("highestPrice") or price)
    target_index = {"TP1": 0, "TP2": 1, "TP3": 2}.get(event_type)
    target = (track.get("targets") or [None, None, None])[target_index] if target_index is not None else track.get("effectiveStop")
    realized = round((price / entry - 1) * 100, 2) if entry else 0.0
    maximum = round((high / entry - 1) * 100, 2) if entry else 0.0
    actions = {
        "TP1": "TP1 görüldü: stop maliyete çekildi; yeni hedefler izleniyor.",
        "TP2": "TP2 görüldü: stop TP1 seviyesine çekildi; yeni hedef izleniyor.",
        "TP3": "TP3 görüldü: pozisyon planı tamamlandı; kademeli kâr alma değerlendirilebilir.",
        "TRAILING_STOP": "Kârlı stop tetiklendi: korunan kârla takip sona erdi.",
        "STOP": "Stop seviyesi görüldü: plan dışına çıkmadan işlem kapatıldı.",
    }
    title = {"TP1": "TP1 HEDEFİ GÖRÜLDÜ", "TP2": "TP2 HEDEFİ GÖRÜLDÜ", "TP3": "TP3 HEDEFİ GÖRÜLDÜ", "TRAILING_STOP": "KÂRLI STOP TETİKLENDİ", "STOP": "STOP TETİKLENDİ"}[event_type]
    message = f"{title}\n{track.get('ticker')} · {track.get('strategy') or 'Model'}\nGiriş: {entry:.2f} TL · Gerçekleşen: {price:.2f} TL · Getiri: {realized:+.2f}%\n{actions[event_type]}"
    delivered = _notify(message)
    row = {
        "timestamp": now, "ticker": track.get("ticker"), "price": price,
        "strategy": track.get("strategy"), "score": track.get("score"),
        "message": message, "status": "sent" if delivered else "local",
        "eventType": event_type, "eventTitle": title, "entryPrice": entry,
        "targetPrice": target, "signalAt": track.get("startedAt"),
        "realizedAt": now, "elapsedSeconds": max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(track["startedAt"])).total_seconds())),
        "realizedReturn": realized, "maxPrice": high, "maxReturn": maximum,
        "action": actions[event_type],
    }
    try:
        rows = json.loads(NOTIFICATION_LOG_PATH.read_text(encoding="utf-8")) if NOTIFICATION_LOG_PATH.exists() else []
        rows = rows if isinstance(rows, list) else []
        rows.insert(0, row)
        NOTIFICATION_LOG_PATH.write_text(json.dumps(rows[:500], ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError, TypeError):
        pass
    track["eventTypes"].append(event_type)
    track.setdefault("events", []).append(row)


def _advance_trade_lifecycle(track: dict, price: float, now: str) -> None:
    """Advance TP/stop state from delayed prices. It never creates or executes an order."""
    if track.get("closed"):
        return
    targets = [float(value) for value in (track.get("targets") or []) if value not in (None, "")]
    entry = float(track.get("startPrice") or price)
    stop = float(track.get("initialStop") or track.get("effectiveStop") or 0)
    for index, target in enumerate(targets[:3]):
        event = f"TP{index + 1}"
        if price >= target and event not in set(track.get("eventTypes", [])):
            _append_trade_event(track, event, price, now)
            if index == 0:
                track["effectiveStop"] = max(stop, entry)
            elif index == 1:
                track["effectiveStop"] = max(float(track.get("effectiveStop") or stop), targets[0])
            else:
                track["effectiveStop"] = max(float(track.get("effectiveStop") or stop), targets[1] if len(targets) > 1 else entry)
    effective_stop = float(track.get("effectiveStop") or stop)
    if effective_stop > 0 and price <= effective_stop:
        protected = any(event in set(track.get("eventTypes", [])) for event in ("TP1", "TP2", "TP3"))
        _append_trade_event(track, "TRAILING_STOP" if protected and effective_stop >= entry else "STOP", price, now)
        track["closed"] = True


def opportunity_snapshot(payload: dict) -> list[dict]:
    opportunities = []
    for stock in payload.get("stocks", []):
        delayed = stock.get("delayedQuote") or {}
        if stock.get("recommendation") != "OPEN" or not delayed.get("price"):
            continue
        low, high = stock.get("entryZoneLow"), stock.get("entryZoneHigh")
        price = float(delayed["price"])
        if low is None or high is None or not (float(low) <= price <= float(high)):
            continue
        notes = stock.get("analystNotes", [])
        analyst_message = next((note.get("Alarm Açıklaması / Talimatı") or note.get("Özel Açıklamalar / Analiz Notları") for note in notes if note.get("Alarm Açıklaması / Talimatı") or note.get("Özel Açıklamalar / Analiz Notları")), None)
        opportunities.append({"ticker": stock["ticker"], "price": price, "score": stock.get("modelScore"), "strategy": stock.get("strategy"), "entry": [low, high], "stop": stock.get("stop"), "targets": stock.get("targets"), "analystNotes": notes, "analystMessage": analyst_message})
    return opportunities


def manual_opportunity_snapshot(payload: dict) -> list[dict]:
    selected = set(manual_tracking())
    rows = []
    for stock in payload.get("stocks", []):
        if stock.get("ticker") not in selected:
            continue
        quote = stock.get("delayedQuote") or {}
        price = quote.get("price") or stock.get("price")
        if not price:
            continue
        notes = stock.get("analystNotes", [])
        analyst_message = next((note.get("Alarm Açıklaması / Talimatı") or note.get("Özel Açıklamalar / Analiz Notları") for note in notes if note.get("Alarm Açıklaması / Talimatı") or note.get("Özel Açıklamalar / Analiz Notları")), None)
        rows.append({"ticker": stock["ticker"], "price": float(price), "score": stock.get("modelScore"), "strategy": "Manuel analist takibi", "entry": [stock.get("entryZoneLow") or price, stock.get("entryZoneHigh") or price], "stop": stock.get("stop"), "targets": stock.get("targets") or [price], "analystMessage": analyst_message, "manual": True})
    return rows


def run_once() -> list[dict]:
    try:
        # The dashboard must remain responsive. The scanner itself refreshes on its
        # own cache interval; forcing a complete BIST100 network scan here could
        # lock the first page load for minutes.
        payload = scan_market()
        opportunities = opportunity_snapshot(payload)
        existing = {item["ticker"] for item in opportunities}
        opportunities.extend(item for item in manual_opportunity_snapshot(payload) if item["ticker"] not in existing)
        tracks = _record_tracking(payload, opportunities)
        state = _load_state()
        changed = False
        for item in opportunities:
            key = f"manual|{item['ticker']}" if item.get("manual") else f"{item['ticker']}|{item['strategy']}|{item['entry'][0]}|{item['entry'][1]}"
            if state.get(item['ticker']) == key:
                continue
            message = (
                f"{item['ticker']} · {item.get('analystMessage') or item['strategy']} · puan {item['score']}\n"
                f"15 dk gecikmeli fiyat: {item['price']}\n"
                f"Giriş: {item['entry'][0]}–{item['entry'][1]} · Stop: {item['stop']} · "
                f"TP1: {item['targets'][0]}"
            )
            # A signal is deduplicated only after the notification is delivered.
            delivered = _notify(message)
            _append_notification_log(item, message, delivered)
            if delivered:
                state[item['ticker']] = key
                changed = True
        if changed:
            _save_state(state)
        with _status_lock:
            _status.update({"running": True, "lastRun": datetime.now().astimezone().isoformat(timespec="seconds"), "lastError": None, "opportunities": opportunities, "tracking": list(tracks.values()), "notificationsEnabled": bool(os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()), "topic": os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()})
        return opportunities
    except Exception as exc:
        with _status_lock:
            _status.update({"running": True, "lastRun": datetime.now().astimezone().isoformat(timespec="seconds"), "lastError": str(exc)})
        raise


def worker_status() -> dict:
    with _status_lock:
        return dict(_status)


def notification_log(limit: int = 200) -> list[dict]:
    try:
        rows = json.loads(NOTIFICATION_LOG_PATH.read_text(encoding="utf-8")) if NOTIFICATION_LOG_PATH.exists() else []
        if not isinstance(rows, list):
            return []
        deduped = []
        failed_tickers = set()
        for row in rows:
            if row.get("status") == "not_sent":
                ticker = row.get("ticker")
                if ticker in failed_tickers:
                    continue
                failed_tickers.add(ticker)
            deduped.append(row)
        return deduped[: max(1, min(int(limit), 500))]
    except (OSError, ValueError, TypeError):
        return []


def tracking_log(limit: int = 200) -> list[dict]:
    rows = list(_load_tracking().values())
    rows.sort(key=lambda item: item.get("lastAt", ""), reverse=True)
    return rows[: max(1, min(int(limit), 500))]


def _load_tracking() -> dict[str, dict]:
    try:
        value = json.loads(TRACKING_LOG_PATH.read_text(encoding="utf-8")) if TRACKING_LOG_PATH.exists() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_tracking(value: dict[str, dict]) -> None:
    TRACKING_LOG_PATH.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _record_tracking(payload: dict, opportunities: list[dict]) -> dict[str, dict]:
    tracks = _load_tracking()
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    new_by_ticker = {item["ticker"]: item for item in opportunities}
    stock_by_ticker = {item.get("ticker"): item for item in payload.get("stocks", [])}
    for ticker, item in new_by_ticker.items():
        quote = stock_by_ticker.get(ticker, {}).get("delayedQuote") or {}
        price = float(quote.get("price") or item.get("price"))
        if ticker not in tracks:
            tracks[ticker] = {
                "ticker": ticker,
                "strategy": item.get("strategy"),
                "score": item.get("score"),
                "analystMessage": item.get("analystMessage"),
                "startedAt": now,
                "startPrice": price,
                "lastAt": now,
                "lastPrice": price,
                "changePercent": 0.0,
                "targets": item.get("targets") or [],
                "initialStop": item.get("stop"),
                "effectiveStop": item.get("stop"),
                "highestPrice": price,
                "highestAt": now,
                "eventTypes": [],
                "events": [],
                "closed": False,
                "updates": [{"timestamp": now, "price": price}],
            }
        elif item.get("analystMessage") and not tracks[ticker].get("analystMessage"):
            tracks[ticker]["analystMessage"] = item.get("analystMessage")
    for ticker, track in tracks.items():
        stock = stock_by_ticker.get(ticker)
        if not stock:
            continue
        quote = stock.get("delayedQuote") or {}
        price = quote.get("price") or stock.get("price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        if price != float(track.get("lastPrice", 0)):
            track.setdefault("updates", []).append({"timestamp": now, "price": price})
            track["updates"] = track["updates"][-100:]
        track["lastAt"] = now
        track["lastPrice"] = price
        if price >= float(track.get("highestPrice") or price):
            track["highestPrice"] = price
            track["highestAt"] = now
        start = float(track.get("startPrice") or price)
        track["changePercent"] = round((price / start - 1) * 100, 2) if start else 0.0
        _advance_trade_lifecycle(track, price, now)
    _save_tracking(tracks)
    return tracks


if __name__ == "__main__":
    while True:
        try:
            print(json.dumps(run_once(), ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        time.sleep(INTERVAL_SECONDS)
