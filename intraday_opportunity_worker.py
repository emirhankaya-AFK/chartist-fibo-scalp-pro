"""15-minute delayed opportunity poller.

It never places orders. Notifications are opt-in via NTFY_TOPIC and NTFY_TOKEN.
"""
from __future__ import annotations

import json
import hashlib
import os
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from threading import Lock

from commodity_groups import COMMODITY_GROUPS
from market_scanner import intraday_commodity_snapshots, scan_market

TR_TZ = timezone(timedelta(hours=3))

def get_tr_now() -> datetime:
    """Returns current Turkey local time (UTC+3)."""
    return datetime.now(TR_TZ)


INTERVAL_SECONDS = int(os.getenv("OPPORTUNITY_INTERVAL_SECONDS", "60"))
SUMMARY_GRACE_MINUTES = int(os.getenv("SUMMARY_GRACE_MINUTES", "10"))
ANALYST_PROXIMITY_PCT = float(os.getenv("ANALYST_PROXIMITY_PCT", "0.75"))
COMMODITY_SPIKE_PCT = float(os.getenv("COMMODITY_SPIKE_PCT", "0.50"))
SEND_INDIVIDUAL_OPPORTUNITY_ALERTS = os.getenv(
    "SEND_INDIVIDUAL_OPPORTUNITY_ALERTS", "0"
).strip().lower() in {"1", "true", "yes"}
ENABLE_TELEGRAM_NOTIFICATIONS = os.getenv(
    "ENABLE_TELEGRAM_NOTIFICATIONS", "0"
).strip().lower() in {"1", "true", "yes"}
STATE_PATH = Path(__file__).with_name("intraday_alert_state.json")
NOTIFICATION_LOG_PATH = Path(__file__).with_name("notification_log.json")
NOTIFICATION_AUDIT_PATH = Path(
    os.getenv(
        "NOTIFICATION_AUDIT_PATH",
        str(Path(__file__).with_name("data") / "notification_audit.jsonl"),
    )
)
TRACKING_LOG_PATH = Path(__file__).with_name("tracking_log.json")
MANUAL_TRACKING_PATH = Path(__file__).with_name("manual_tracking.json")
OGUZ_ARSIV_PATH = Path(__file__).with_name("OGUZ_ANALIZ_ARSIVI.json")
MERGEN_ARSIV_PATH = Path(__file__).with_name("AHMET_MERGEN_ANALIZ_ARSIVI.json")
EXCEL_PATH = Path(__file__).with_name("Hisselerin_Teknik_Verileri.xlsx")
DEFAULT_NTFY_TOPIC = "emirkan_bist_alarm"
_status_lock = Lock()
_run_lock = Lock()
_notification_log_lock = Lock()
_delivery_result_lock = Lock()
_delivery_results: dict[str, dict] = {}
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


def _delivery_key(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def _remember_delivery_result(message: str, result: dict) -> None:
    with _delivery_result_lock:
        _delivery_results[_delivery_key(message)] = result


def _take_delivery_result(message: str, delivered: bool) -> dict:
    with _delivery_result_lock:
        result = _delivery_results.pop(_delivery_key(message), None)
    if result:
        return result
    return {
        "attemptedAt": get_tr_now().isoformat(timespec="seconds"),
        "deliveryStatus": "sent" if delivered else "failed",
        "channels": {},
        "reason": "Teslimat ayrıntısı alınamadı.",
    }


def _persist_notification_row(row: dict) -> None:
    """Keep a UI history and an append-only forensic delivery ledger."""
    try:
        with _notification_log_lock:
            rows = json.loads(NOTIFICATION_LOG_PATH.read_text(encoding="utf-8")) if NOTIFICATION_LOG_PATH.exists() else []
            rows = rows if isinstance(rows, list) else []
            rows.insert(0, row)
            NOTIFICATION_LOG_PATH.write_text(json.dumps(rows[:2000], ensure_ascii=False), encoding="utf-8")

            NOTIFICATION_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with NOTIFICATION_AUDIT_PATH.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (OSError, ValueError, TypeError):
        pass


def _append_notification_log(item: dict, message: str, delivered: bool) -> None:
    delivery = _take_delivery_result(message, delivered)
    row = {
        "timestamp": delivery.get("attemptedAt") or get_tr_now().isoformat(timespec="seconds"),
        "ticker": item.get("ticker"),
        "price": item.get("price"),
        "strategy": item.get("strategy"),
        "score": item.get("score"),
        "message": message,
        "status": delivery.get("deliveryStatus") or ("sent" if delivered else "failed"),
        "reason": delivery.get("reason", ""),
        "attempts": 1,
        "delivery": delivery,
    }
    context = item.get("auditContext")
    if isinstance(context, dict) and context:
        row["context"] = context
    _persist_notification_row(row)


def _append_system_notification_log(
    category: str,
    message: str,
    delivered: bool,
    *,
    ticker: str | None = None,
    price: float | None = None,
    score: float | None = None,
    context: dict | None = None,
) -> None:
    """Record scheduled, commodity and analyst notifications for diagnostics."""
    item = {
        "ticker": ticker or category,
        "price": price,
        "strategy": category,
        "score": score,
        "auditContext": context or {},
    }
    _append_notification_log(item, message, delivered)


def is_notification_window_open() -> bool:
    """Returns True ONLY if Turkey Local Time (UTC+3) is between 09:50 and 18:15 on weekdays."""
    now = get_tr_now()
    if now.weekday() >= 5:  # Weekend
        return False
    start_time = now.replace(hour=9, minute=50, second=0, microsecond=0)
    end_time = now.replace(hour=18, minute=15, second=0, microsecond=0)
    return start_time <= now <= end_time


def _notify(message: str) -> bool:
    attempted_at = get_tr_now().isoformat(timespec="seconds")
    result = {
        "attemptedAt": attempted_at,
        "deliveryStatus": "failed",
        "channels": {},
        "reason": "",
    }
    if not is_notification_window_open():
        result["deliveryStatus"] = "blocked"
        result["reason"] = "Bildirim penceresi kapalı (hafta içi 09:50–18:15 TR)."
        _remember_delivery_result(message, result)
        return False
    sent = False
    errors = []
    topic = os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()
    if topic:
        url = f"https://ntfy.sh/{topic}"
        is_oguz = "oğuz" in message.lower() or "oguz" in message.lower()
        headers = {
            "Title": "OĞUZ ANALİST ALARMI" if is_oguz else "Chartist Fibo-Scalp Pro",
            "Priority": "max" if is_oguz else "high",
            "Tags": "rotating_light,chart_with_upwards_trend" if is_oguz else "chart_with_upwards_trend,bell",
        }
        token = os.getenv("NTFY_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, data=message.encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                provider_id = None
                try:
                    response_body = json.loads(response.read().decode("utf-8"))
                    provider_id = response_body.get("id")
                except (ValueError, UnicodeDecodeError, AttributeError):
                    pass
                result["channels"]["ntfy"] = {
                    "status": "sent",
                    "httpStatus": getattr(response, "status", 200),
                    "messageId": provider_id,
                    "topic": topic,
                }
                sent = True
        except Exception as exc:
            result["channels"]["ntfy"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"ntfy: {type(exc).__name__}: {exc}")
            print(f"[NOTIFY NTFY ERROR] {exc}")
    else:
        errors.append("NTFY_TOPIC eksik")
        result["channels"]["ntfy"] = {"status": "not_configured"}

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if ENABLE_TELEGRAM_NOTIFICATIONS and bot_token and chat_id:
        try:
            tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(tg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                result["channels"]["telegram"] = {
                    "status": "sent",
                    "httpStatus": getattr(response, "status", 200),
                }
                sent = True
        except Exception as exc:
            result["channels"]["telegram"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"telegram: {type(exc).__name__}: {exc}")
            print(f"[NOTIFY TELEGRAM ERROR] {type(exc).__name__}: {exc}")

    result["deliveryStatus"] = "sent" if sent else "failed"
    result["reason"] = "" if sent else "; ".join(errors) or "Hiçbir bildirim kanalı teslimatı doğrulamadı."
    _remember_delivery_result(message, result)
    return sent


def send_audited_notification(
    message: str,
    *,
    category: str,
    ticker: str | None = None,
    price: float | None = None,
    score: float | None = None,
    context: dict | None = None,
) -> bool:
    """Send once and always record the exact message, trigger and provider result."""
    delivered = _notify(message)
    _append_system_notification_log(
        category,
        message,
        delivered,
        ticker=ticker,
        price=price,
        score=score,
        context=context,
    )
    return delivered


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
    delivery = _take_delivery_result(message, delivered)
    row["delivery"] = delivery
    row["reason"] = delivery.get("reason", "")
    if not delivered and delivery.get("deliveryStatus") in {"blocked", "failed"}:
        row["status"] = delivery["deliveryStatus"]
    _persist_notification_row(row)
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


def _load_analyst_levels() -> list[dict]:
    """Load analyst support/resistance/entry levels from Excel and OGUZ_ANALIZ_ARSIVI.json."""
    levels = []

    # 1. Load from OGUZ_ANALIZ_ARSIVI.json
    try:
        if OGUZ_ARSIV_PATH.exists():
            rows = json.loads(OGUZ_ARSIV_PATH.read_text(encoding="utf-8"))
            for row in rows:
                ticker = row.get("ticker", "").upper().strip()
                if not ticker:
                    continue
                entry = row.get("entry_level")
                note = row.get("note", "")
                source = "Oğuz Çelik" if "Oğuz" in note else "Analist"
                entry_values = []
                if entry not in (None, ""):
                    entry_values.append(float(entry))
                for zone_value in row.get("entry_zone") or []:
                    try:
                        parsed_zone_value = float(zone_value)
                    except (TypeError, ValueError):
                        continue
                    if parsed_zone_value not in entry_values:
                        entry_values.append(parsed_zone_value)
                for entry_value in entry_values:
                    levels.append({
                        "ticker": ticker,
                        "source": source,
                        "entry": entry_value,
                        "support": None,
                        "resistance": None,
                        "note": note,
                        "name": row.get("name", ticker),
                    })
    except Exception:
        pass

    # 2. Load structured Ahmet Mergen transcript archive.
    try:
        if MERGEN_ARSIV_PATH.exists():
            rows = json.loads(MERGEN_ARSIV_PATH.read_text(encoding="utf-8"))
            for row in rows:
                ticker = str(row.get("ticker", "")).upper().strip()
                if not ticker:
                    continue
                levels.append({
                    "ticker": ticker,
                    "source": row.get("source") or "Ahmet Mergen",
                    "entry": row.get("entry_level"),
                    "support": row.get("support"),
                    "resistance": row.get("resistance"),
                    "note": row.get("note", ""),
                    "name": row.get("name", ticker),
                })
    except (OSError, ValueError, TypeError) as exc:
        print(f"[MERGEN ARCHIVE ERROR] {type(exc).__name__}: {exc}")

    # 3. Load from Excel
    try:
        if EXCEL_PATH.exists():
            import openpyxl
            wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
            ws = wb.active
            for r in range(4, ws.max_row + 1):
                ticker = ws.cell(row=r, column=2).value
                if not ticker:
                    continue
                ticker = str(ticker).upper().strip()
                name = ws.cell(row=r, column=3).value or ""
                entry = ws.cell(row=r, column=4).value
                support_raw = ws.cell(row=r, column=5).value
                resistance_raw = ws.cell(row=r, column=6).value
                note = ws.cell(row=r, column=8).value or ""

                source = "Oğuz Çelik" if "Oğuz" in note else "Ahmet Mergen" if "Mergen" in note else "Analist"

                # Parse support/resistance (may be strings like "1.34 - 1.35 TL")
                support_val = None
                resistance_val = None
                try:
                    if support_raw:
                        s = str(support_raw).replace("TL", "").replace(",", ".").strip()
                        parts = [p.strip() for p in s.split("-") if p.strip()]
                        support_val = float(parts[0]) if parts else None
                except Exception:
                    pass
                try:
                    if resistance_raw:
                        s = str(resistance_raw).replace("TL", "").replace(",", ".").strip()
                        parts = [p.strip() for p in s.split("-") if p.strip()]
                        resistance_val = float(parts[-1]) if parts else None
                except Exception:
                    pass

                # Only add if we don't already have this ticker from OGUZ or if Excel has extra data
                existing_tickers = {l["ticker"] for l in levels}
                if ticker not in existing_tickers:
                    levels.append({"ticker": ticker, "source": source, "entry": float(entry) if entry else None, "support": support_val, "resistance": resistance_val, "note": note, "name": name})
                else:
                    # Merge Excel support/resistance into existing
                    for l in levels:
                        if l["ticker"] == ticker:
                            if support_val and not l.get("support"):
                                l["support"] = support_val
                            if resistance_val and not l.get("resistance"):
                                l["resistance"] = resistance_val
                            if note and "Mergen" in note and "Mergen" not in (l.get("note") or ""):
                                l["note"] = l.get("note", "") + " | " + note
                            break
            if "Aktif Alarmlar (Premium)" in wb.sheetnames:
                alarm_ws = wb["Aktif Alarmlar (Premium)"]
                for r in range(4, alarm_ws.max_row + 1):
                    symbol = alarm_ws.cell(row=r, column=1).value
                    rule = str(alarm_ws.cell(row=r, column=3).value or "")
                    target = alarm_ws.cell(row=r, column=4).value
                    active = str(alarm_ws.cell(row=r, column=5).value or "").strip().lower()
                    note = str(alarm_ws.cell(row=r, column=7).value or "")
                    if not symbol or target in (None, "") or active not in {"evet", "yes", "true", "1"}:
                        continue
                    ticker = str(symbol).upper().replace(".IS", "").strip()
                    try:
                        target_value = float(target)
                    except (TypeError, ValueError):
                        continue
                    support = target_value if "<=" in rule else None
                    resistance = target_value if ">=" in rule else None
                    levels.append({
                        "ticker": ticker,
                        "source": "Ahmet Mergen" if "Mergen" in note else "Aktif Alarm",
                        "entry": None,
                        "support": support,
                        "resistance": resistance,
                        "note": note,
                        "name": alarm_ws.cell(row=r, column=2).value or ticker,
                    })
            wb.close()
    except Exception:
        pass

    return levels


def check_analyst_level_alerts(payload: dict) -> None:
    """Check if any stock price is near analyst support/resistance/entry levels and send detailed alerts."""
    analyst_levels = _load_analyst_levels()
    if not analyst_levels:
        return

    state = _load_state()
    today_str = get_tr_now().strftime("%Y-%m-%d")
    changed = False

    stocks_map = {}
    for s in payload.get("stocks", []):
        quote = s.get("delayedQuote") or {}
        price = quote.get("price") or s.get("price")
        if price:
            stocks_map[s["ticker"]] = {"price": float(price), "stock": s}

    index_info = payload.get("index") or {}
    if index_info.get("price"):
        stocks_map["XU100"] = {
            "price": float(index_info["price"]),
            "stock": {"ticker": "XU100", "name": "BIST 100 Endeksi", "modelScore": "—"},
        }

    macro_tickers = {
        "ONS ALTIN ($)": "GC=F",
        "ONS GÜMÜŞ ($)": "SI=F",
        "BRENT PETROL ($)": "BZ=F",
        "BAKIR ($)": "HG=F",
        "GRAM ALTIN (TL)": "GRAMALTIN",
    }
    for macro in payload.get("marketBoard", []):
        ticker = macro_tickers.get(macro.get("label"))
        if ticker and macro.get("value") not in (None, ""):
            stocks_map[ticker] = {
                "price": float(macro["value"]),
                "stock": {"ticker": ticker, "name": macro.get("label"), "modelScore": "—"},
            }

    for level in analyst_levels:
        ticker = level["ticker"]
        if ticker not in stocks_map:
            continue

        price = stocks_map[ticker]["price"]
        stock = stocks_map[ticker]["stock"]
        entry = level.get("entry")
        support = level.get("support")
        resistance = level.get("resistance")
        note = level.get("note") or ""
        source = level.get("source", "Analist")
        name = level.get("name") or stock.get("name") or ticker

        # Alert close to the recorded level. A narrow default avoids very early alerts.
        threshold = max(0.1, ANALYST_PROXIMITY_PCT) / 100.0
        alerts = []

        if entry and abs(price - entry) / entry <= threshold:
            direction = "📗 Giriş seviyesinin TAM ÜZERİNDE" if price >= entry else "📕 Giriş seviyesinin ALTINA düştü"
            diff_pct = round((price / entry - 1) * 100, 2)
            alerts.append({
                "type": "GİRİŞ SEVİYESİ",
                "level": entry,
                "direction": direction,
                "diff_pct": diff_pct,
                "emoji": "🎯"
            })

        if support and abs(price - support) / support <= threshold:
            diff_pct = round((price / support - 1) * 100, 2)
            direction = "🟢 Destek seviyesinde TUTUNUYOR" if price >= support else "🔴 Destek seviyesi KIRILDI!"
            alerts.append({
                "type": "DESTEK SEVİYESİ",
                "level": support,
                "direction": direction,
                "diff_pct": diff_pct,
                "emoji": "🛡️"
            })

        if resistance and abs(price - resistance) / resistance <= threshold:
            diff_pct = round((price / resistance - 1) * 100, 2)
            direction = "🟢 Direnç seviyesi KIRILDI! Yukarı yön açıldı" if price >= resistance else "🟡 Direnç seviyesine YAKIN, satıcı gelebilir"
            alerts.append({
                "type": "DİRENÇ SEVİYESİ",
                "level": resistance,
                "direction": direction,
                "diff_pct": diff_pct,
                "emoji": "🧱"
            })

        for alert in alerts:
            level_key = f"{float(alert['level']):.4f}"
            source_key = str(source).replace(" ", "_")
            alert_key = f"analyst_{ticker}_{source_key}_{alert['type']}_{level_key}_{today_str}"
            if state.get(alert_key):
                continue

            # Build a super detailed message
            model_score = stock.get("modelScore", "—")
            targets = stock.get("targets") or [price, price, price]
            tp1 = targets[0] if len(targets) > 0 else price
            tp2 = targets[1] if len(targets) > 1 else tp1
            tp3 = targets[2] if len(targets) > 2 else tp2
            stop = stock.get("stop", "—")

            message = (
                f"📢 *ANALİST SEVİYE ALARMI*\n"
                f"👤 *Kaynak:* {source}\n\n"
                f"📌 *Hisse:* #{ticker} ({name})\n"
                f"💵 *Güncel Fiyat:* {price:.2f} TL\n"
                f"⭐ *Model Puanı:* {model_score}\n\n"
                f"{alert['emoji']} *{alert['type']}:* {alert['level']:.2f} TL\n"
                f"{alert['direction']}\n"
                f"📊 *Fark:* %{alert['diff_pct']:+.2f}\n\n"
                f"💬 *Analist Notu:*\n{note}\n\n"
                f"🎯 *Model Hedefleri:*\n"
                f"  • TP1: {tp1} TL\n"
                f"  • TP2: {tp2} TL\n"
                f"  • TP3: {tp3} TL\n"
                f"  • Stop: {stop} TL\n\n"
                f"⚠️ *Ne Yapmalı:*\n"
            )

            if alert["type"] == "DESTEK SEVİYESİ":
                if price >= support:
                    message += f"Destek {alert['level']:.2f} TL'de tutuyor. Buradan alım düşünülebilir ama stop {alert['level']:.2f} TL altına konmalı. Kırılırsa uzak dur."
                else:
                    message += f"Destek {alert['level']:.2f} TL kırıldı! Pozisyon varsa stop'u değerlendir. Yeni alım için acele etme, daha aşağı gelebilir."
            elif alert["type"] == "DİRENÇ SEVİYESİ":
                if price >= resistance:
                    message += f"Direnç {alert['level']:.2f} TL kırıldı! Yukarı yön açıldı. Kâr hedeflerine doğru izle. Geri dönerse dikkat."
                else:
                    message += f"Direnç {alert['level']:.2f} TL'ye yaklaştı. Burada satıcı gelebilir. Pozisyon varsa kısmi kâr alma düşünülebilir."
            else:
                message += f"Giriş seviyesi {alert['level']:.2f} TL civarında. Analist bu seviyeyi alım için uygun görmüştü. Stop koyarak değerlendirilebilir."

            # Start an independent analyst-performance record. This remains
            # visible even if Ntfy delivery fails or the model is stale.
            _start_or_update_analyst_track(
                ticker=ticker,
                name=name,
                source=source,
                alert_type=alert["type"],
                level=float(alert["level"]),
                price=price,
                note=note,
                now=get_tr_now().isoformat(timespec="seconds"),
            )
            delivered = _notify(message)
            _append_system_notification_log("analyst-level", message, delivered, ticker=ticker)
            if delivered:
                state[alert_key] = True
                changed = True

    if changed:
        _save_state(state)


def check_and_send_scheduled_summaries(payload: dict) -> None:
    now_dt = get_tr_now()
    today_str = now_dt.strftime("%Y-%m-%d")
    slots = [
        (10, 0, "10:00 (Seans Açılış Özet Bülteni)"),
        (12, 0, "12:00 (Seans Ortası Özet Bülteni)"),
        (14, 0, "14:00 (Öğleden Sonra Özet Bülteni)"),
        (16, 0, "16:00 (Kapanış Öncesi Özet Bülteni)"),
        (18, 0, "18:00 (Seans Kapanış ve Gün Sonu Bülteni)"),
    ]
    slot_name = None
    slot_key = None
    for hour, minute, name in slots:
        target = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        elapsed_minutes = (now_dt - target).total_seconds() / 60.0
        if 0 <= elapsed_minutes < SUMMARY_GRACE_MINUTES:
            slot_name = name
            slot_key = f"summary_{today_str}_{hour:02d}{minute:02d}"
            break

    if not slot_name:
        return

    state = _load_state()
    if state.get(slot_key):
        return  # Already sent for this specific slot today

    index_info = payload.get("index", {})
    xu100_price = index_info.get("price", "—")
    xu100_daily = index_info.get("daily", 0.0)

    index_warning = ""
    try:
        p_val = float(xu100_price)
        if p_val <= 13850:
            index_warning = (
                "\n⚠️ *DİKKAT (Ahmet Mergen):* Endeks 13.850 TL kritik desteğinde! "
                "Eğer 13.230 TL desteği de kırılırsa sonraki durak 12.900 TL veya 12.500 TL seviyeleri olabilir. "
                "Yukarı yönde tepki için 14.250 - 14.254 TL (50 günlük HO) direncinin aşılması gerekir."
            )
        else:
            index_warning = (
                f"\nℹ️ *Endeks Analizi (Ahmet Mergen):* {p_val:,.2f} TL. "
                "14.250 - 14.254 TL direnci aşılırsa yükseliş 14.600 TL veya 14.876 TL seviyelerine doğru yol alabilir. "
                "13.850 TL altı kapanışlarda ise 13.230 TL ve 12.900 TL destekleri takip edilecektir."
            )
    except Exception:
        index_warning = ""

    wind_text = f"BIST100: {xu100_price} TL (%{xu100_daily:+.2f}){index_warning}"

    stocks = payload.get("stocks", [])
    # The scheduled bulletin is a shortlist, not a catalogue. Only show
    # high-conviction OPEN signals; WATCH/weak candidates belong on the site.
    candidates = [
        s for s in stocks
        if s.get("recommendation") == "OPEN"
        and float(s.get("modelScore") or 0) >= 82
        and float((s.get("componentScores") or {}).get("technical") or 0) >= 65
        and float((s.get("componentScores") or {}).get("stop") or 0) >= 60
        and float(s.get("rr") or 0) >= 1.8
        and not any("RİSK" in str(b).upper() or "RISK" in str(b).upper() or "OBO" in str(b).upper() for b in (s.get("badges") or []))
    ]
    top_candidates = sorted(
        candidates,
        key=lambda s: s.get("modelScore", 0),
        reverse=True,
    )[:5]
    
    top_text_list = []
    for s in top_candidates:
        quote = s.get("delayedQuote") or {}
        current_price = quote.get("price") or s.get("price")
        targets = s.get("targets") or [current_price, current_price, current_price]
        tp1 = targets[0] if len(targets) > 0 else current_price
        tp2 = targets[1] if len(targets) > 1 else tp1
        tp3 = targets[2] if len(targets) > 2 else tp2
        stop = s.get("stop", "—")
        badge = s.get("badges", [""])[0] if s.get("badges") else ""
        badge_str = f" ({badge})" if badge else ""
        
        top_text_list.append(
            f"📌 *#{s['ticker']}*{badge_str} — Model Puanı: *{s['modelScore']}* "
            f"({s.get('recommendation', '—')})\n"
            f"  • Güncel Fiyat: {current_price} TL | Stop: {stop} TL\n"
            f"  • Kâr Hedefleri: TP1: {tp1} TL | TP2: {tp2} TL | TP3: {tp3} TL"
        )

    top_text = "\n\n".join(top_text_list) if top_text_list else "Fırsat hisse bulunamadı."

    try:
        from auto_portfolio import load_portfolio
        portfolio = load_portfolio()
        initial = portfolio.get("initial_capital", 10000.0)
        cash = portfolio.get("current_cash", 10000.0)
        positions = portfolio.get("positions", [])
        equity_val = sum(pos.get("current_price", 0) * pos.get("qty", 0) for pos in positions)
        total_val = cash + equity_val
        net_pnl = total_val - initial
        net_pnl_pct = (net_pnl / initial) * 100

        portfolio_text = (
            f"• Toplam Bakiye: {total_val:,.2f} TL\n"
            f"• Boştaki Nakit: {cash:,.2f} TL ({len(positions)} Aktif Pozisyon)\n"
            f"• Net K/Z: {net_pnl:+.2f} TL (%{net_pnl_pct:+.2f})"
        )
    except Exception:
        portfolio_text = "Portföy bilgisi alınamadı."

    message = (
        f"🕒 *MODEL EN YÜKSEK PUAN ÖZET BÜLTENİ*\n"
        f"📅 *Zaman:* {today_str} — {slot_name}\n\n"
        f"📈 *Piyasa Yönü:*\n{wind_text}\n\n"
        f"🤖 *10K Robot Portföy Karnesi:*\n{portfolio_text}\n\n"
        f"⭐ *Modeldeki En Yüksek Puanlı Top 5 Hisse:*\n\n{top_text}\n\n"
        f"🏷️ *Sözlük:* SK3 = 3'lü Süper Konsensüs | ÇAO = Çifte Algo Onayı"
    )

    delivered = _notify(message)
    _append_system_notification_log("scheduled-summary", message, delivered)
    if delivered:
        state[slot_key] = True
        _save_state(state)


def check_intraday_price_movements(payload: dict) -> None:
    """Check if any tracked stock has reached a new 0.5% gain/loss milestone (+1.0%, +1.5%, +2.0%, +2.5%, etc.) and push alerts."""
    import math
    state = _load_state()
    today_str = get_tr_now().strftime("%Y-%m-%d")
    changed = False

    for stock in payload.get("stocks", []):
        ticker = stock.get("ticker")
        quote = stock.get("delayedQuote") or {}
        price = quote.get("price") or stock.get("price")
        prev_close = (stock.get("officialOhlc") or {}).get("previousClose") or stock.get("previousClose") or price

        if not ticker or not price or not prev_close or float(prev_close) <= 0:
            continue

        price = float(price)
        prev_close = float(prev_close)
        change_pct = round((price / prev_close - 1) * 100, 2)

        steps = []
        # Positive gain steps starting from +1.0% with 0.5% increments
        if change_pct >= 1.0:
            current_step = round(math.floor(change_pct * 2.0) / 2.0, 1)
            step_val = 1.0
            while step_val <= current_step:
                if step_val >= 5.0:
                    emoji_title = "🚀 *GÜÇLÜ RALLİ HAREKETİ*"
                elif step_val >= 3.0:
                    emoji_title = "🔥 *YÜKSEK İVME KAZANDI*"
                elif step_val >= 2.0:
                    emoji_title = "📈 *POZİTİF YÜKSELİŞ HAREKETİ*"
                else:
                    emoji_title = "📊 *KAZANÇ EŞİĞİ AŞILDI*"
                
                steps.append((step_val, emoji_title))
                step_val = round(step_val + 0.5, 1)

        # Downside retreat steps starting from -2.0% with 0.5% increments
        elif change_pct <= -2.0:
            current_step = round(math.ceil(change_pct * 2.0) / 2.0, 1)
            step_val = -2.0
            while step_val >= current_step:
                steps.append((step_val, "⚠️ *SEANS İÇİ GERİ ÇEKİLME*"))
                step_val = round(step_val - 0.5, 1)

        for step_val, title in steps:
            tag_str = f"{step_val:+.1f}%"
            alert_key = f"move_step_{ticker}_{tag_str}_{today_str}"
            if state.get(alert_key):
                continue

            model_score = stock.get("modelScore", "—")
            notes = stock.get("analystNotes", [])
            note_str = next((n.get("Alarm Açıklaması / Talimatı") or n.get("Özel Açıklamalar / Analiz Notları") for n in notes if n.get("Alarm Açıklaması / Talimatı") or n.get("Özel Açıklamalar / Analiz Notları")), "Model Takibi")

            message = (
                f"{title} (Eşik: %{step_val:+.1f})\n\n"
                f"📌 *Hisse:* #{ticker}\n"
                f"💵 *Güncel Fiyat:* {price:.2f} TL (Günlük: %{change_pct:+.2f})\n"
                f"⭐ *Model Puanı:* {model_score}\n"
                f"💬 *Analist / Strateji Notu:*\n{note_str}\n\n"
                f"📊 *Önceki Kapanış:* {prev_close:.2f} TL"
            )

            delivered = _notify(message)
            _append_system_notification_log(
                "price-movement",
                message,
                delivered,
                ticker=ticker,
                price=price,
                score=model_score if isinstance(model_score, (int, float)) else None,
                context={
                    "trigger": "stock_daily_milestone",
                    "thresholdPercent": step_val,
                    "stockDailyPercent": change_pct,
                    "previousClose": prev_close,
                    "priceDataMode": "BIST yaklaşık 15 dk gecikmeli",
                },
            )
            if delivered:
                state[alert_key] = True
                changed = True

    if changed:
        _save_state(state)


COMMODITY_MAPPING = COMMODITY_GROUPS


def check_opening_diagnostic_alert(payload: dict) -> None:
    """Send opening market commodity diagnostic and technical health check bulletin at 09:55 TR local time."""
    now_dt = get_tr_now()
    today_str = now_dt.strftime("%Y-%m-%d")
    target = now_dt.replace(hour=9, minute=55, second=0, microsecond=0)
    elapsed_minutes = (now_dt - target).total_seconds() / 60.0

    # The 60-second worker should deliver at 09:55; a short grace handles startup delay.
    if not (0 <= elapsed_minutes < SUMMARY_GRACE_MINUTES):
        return

    state = _load_state()
    diag_key = f"opening_diag_{today_str}"
    if state.get(diag_key):
        return  # Already sent opening diagnostic today

    market_board = payload.get("marketBoard", [])
    gold_item = next((m for m in market_board if m.get("label") == "ONS ALTIN ($)"), {})
    silver_item = next((m for m in market_board if m.get("label") == "ONS GÜMÜŞ ($)"), {})
    brent_item = next((m for m in market_board if m.get("label") == "BRENT PETROL ($)"), {})
    copper_item = next((m for m in market_board if m.get("label") == "BAKIR ($)"), {})

    def _fmt_comm(item: dict) -> str:
        val = item.get("value")
        daily = item.get("daily")
        if val is None or daily is None:
            return "—"
        return f"{val:,.2f} $ (*%{daily:+.2f}*)"

    gold_str = _fmt_comm(gold_item)
    silver_str = _fmt_comm(silver_item)
    brent_str = _fmt_comm(brent_item)
    copper_str = _fmt_comm(copper_item)

    message = (
        f"🌅 *SEANS AÇILIŞI EMTİA & TEKNİK ANALİZ SAĞLIK KONTROLÜ*\n"
        f"📅 *Tarih:* {today_str} — 09:55 TR (Seans Açılış Kontrolü)\n\n"
        f"🟡 *Ons Altın:* {gold_str}\n"
        f"⚪ *Ons Gümüş:* {silver_str}\n"
        f"🛢️ *Brent Petrol:* {brent_str}\n"
        f"🔴 *Bakır Futures:* {copper_str}\n\n"
        f"✅ *Piyasa Tarama Motoru:* %100 Aktif ve Taramalar Başlatıldı.\n"
        f"🎯 *Korelasyon Eşiği:* ≥ %1.00 Emtia Yükselişlerinde Yüksek Güvenli Alarmlar Gönderilecek!"
    )

    delivered = _notify(message)
    _append_system_notification_log("opening-diagnostic", message, delivered)
    if delivered:
        state[diag_key] = True
        _save_state(state)


def check_commodity_correlation_alerts(payload: dict) -> None:
    """Send positive 0.5-point commodity milestones and rapid-rise correlation alerts."""
    import math

    market_board = payload.get("marketBoard", [])
    if not market_board:
        return

    state = _load_state()
    today_str = get_tr_now().strftime("%Y-%m-%d")
    changed = False

    stocks_dict = {s.get("ticker"): s for s in payload.get("stocks", [])}

    for comm in COMMODITY_MAPPING:
        macro_item = next((m for m in market_board if m.get("label") == comm["macro_label"]), None)
        if not macro_item or macro_item.get("daily") is None:
            continue

        try:
            comm_pct = float(macro_item["daily"])
            comm_val = float(macro_item["value"])
        except (TypeError, ValueError):
            continue

        short_change_raw = macro_item.get("shortChange")
        try:
            short_change = float(short_change_raw) if short_change_raw is not None else None
        except (TypeError, ValueError):
            short_change = None

        current_step = None
        step_key = None
        if comm_pct >= comm["min_move"]:
            current_step = round(math.floor(comm_pct * 2.0) / 2.0, 1)
            step_key = f"commodity_step_{comm['name']}_{today_str}_{current_step:.1f}"

        spike_bucket = int(get_tr_now().timestamp() // (15 * 60))
        spike_key = f"commodity_spike_{comm['name']}_{today_str}_{spike_bucket}"
        is_new_step = bool(step_key and not state.get(step_key))
        is_new_spike = bool(
            short_change is not None
            and short_change >= COMMODITY_SPIKE_PCT
            and not state.get(spike_key)
        )
        if not is_new_step and not is_new_spike:
            continue

        stock_lines = []
        lagging_stocks = []
        leading_stocks = []
        for rel in comm["related"]:
            ticker = rel["ticker"]
            stock_obj = stocks_dict.get(ticker)
            if not stock_obj:
                continue

            quote = stock_obj.get("delayedQuote") or {}
            stock_price = float(quote.get("price") or stock_obj.get("price") or 0)
            stock_pct = float(stock_obj.get("daily", 0) or 0)
            if stock_pct >= comm_pct:
                tag = "🚀 (Önden Tepki)"
                leading_stocks.append(f"#{ticker} (*%{stock_pct:+.2f}*)")
            elif stock_pct < (comm_pct * 0.5):
                tag = "⚡ (GECİKMELİ FIRSAT)"
                lagging_stocks.append(f"#{ticker} (*%{stock_pct:+.2f}*)")
            else:
                tag = "📈 (Paralel Tepki)"
            stock_lines.append(
                f"  • *#{ticker}* ({rel['name']}): {stock_price:.2f} TL | "
                f"Günlük: *%{stock_pct:+.2f}* {tag}"
            )

        insights = []
        if leading_stocks:
            insights.append(
                f"• {comm['name']} *%{comm_pct:+.2f}* iken "
                f"{', '.join(leading_stocks)} önden güçlü yükseldi."
            )
        if lagging_stocks:
            insights.append(
                f"• ⚡ *GECİKMELİ TEPKİ FIRSATI:* {', '.join(lagging_stocks)} "
                "emtia yükselişine henüz güçlü tepki vermedi."
            )
        if not insights:
            insights.append("• İlişkili hisselerde belirgin bir gecikme saptanmadı.")

        trigger_lines = []
        if is_new_step:
            trigger_lines.append(f"Günlük basamak: *%{current_step:+.1f}*")
        if is_new_spike:
            window = int(macro_item.get("shortWindowMinutes") or 15)
            trigger_lines.append(f"Ani {window} dk hareket: *%{short_change:+.2f}*")

        stock_block = "\n".join(stock_lines) if stock_lines else "  • İlişkili BIST hissesi verisi henüz alınamadı."
        insight_text = "\n".join(insights)
        message = (
            f"{comm['icon']} *EMTİA YÜKSELİŞ & KORELASYON ALARMI*\n\n"
            f"📊 *Emtia:* {comm['name']} ({macro_item['label']})\n"
            f"💵 *Seviye:* {comm_val:,.2f} $ | Günlük: *%{comm_pct:+.2f}*\n"
            f"⏱️ {' | '.join(trigger_lines)}\n"
            f"🕓 Veri zamanı: {macro_item.get('timestamp', '—')}\n\n"
            f"🔗 *İlişkili hisseler (BIST yaklaşık 15 dk gecikmeli):*\n{stock_block}\n\n"
            f"💡 *Kıyaslama:*\n{insight_text}"
        )

        delivered = _notify(message)
        _append_system_notification_log(
            "commodity",
            message,
            delivered,
            ticker=comm["name"],
            price=comm_val,
            context={
                "trigger": "commodity_correlation",
                "commodity": comm["name"],
                "commodityLabel": macro_item.get("label"),
                "commodityDailyPercent": comm_pct,
                "commodityShortPercent": short_change,
                "commodityTimestamp": macro_item.get("timestamp"),
                "milestonePercent": current_step if is_new_step else None,
                "rapidRise": is_new_spike,
                "relatedTickers": [item["ticker"] for item in comm["related"]],
                "laggingTickers": lagging_stocks,
                "leadingTickers": leading_stocks,
            },
        )
        if delivered:
            if current_step is not None:
                step = float(comm["min_move"])
                while step <= current_step:
                    state[f"commodity_step_{comm['name']}_{today_str}_{step:.1f}"] = True
                    step = round(step + 0.5, 1)
            if is_new_spike:
                state[spike_key] = True
            changed = True

    if changed:
        _save_state(state)


def _run_once_unlocked() -> list[dict]:
    try:
        payload = dict(scan_market())
        commodity_rows = intraday_commodity_snapshots()
        if commodity_rows:
            board_by_label = {
                item.get("label"): dict(item)
                for item in payload.get("marketBoard", [])
                if item.get("label")
            }
            for item in commodity_rows:
                board_by_label[item["label"]] = item
            payload["marketBoard"] = list(board_by_label.values())

        stock_data_is_fresh = not payload.get("staleData", False)
        # Analyst-only mode: Oğuz and Ahmet Mergen levels are the only
        # notification source and the only new tracking records.
        opportunities = []
        tracks = _load_tracking()
        state = _load_state()
        today_str = get_tr_now().strftime("%Y-%m-%d")
        changed = False
        notification_candidates = []
        for item in notification_candidates:
            key = f"{today_str}|manual|{item['ticker']}" if item.get("manual") else f"{today_str}|{item['ticker']}|{item['strategy']}"
            if state.get(key):
                continue

            stock_obj = next((s for s in payload.get("stocks", []) if s.get("ticker") == item["ticker"]), None)
            is_manual = item.get("manual", False)
            score = item.get("score", 0) or 0

            consensus_badges = []
            if stock_obj and stock_obj.get("badges"):
                # Filter positive consensus badges (SK3, ÇAO), excluding risk tags
                consensus_badges = [b for b in stock_obj["badges"] if ("SK" in b or "ÇAO" in b) and "RİSK" not in b and "OBO" not in b]

            badge_info = ""
            if consensus_badges:
                badge_info = f"\n🏷️ *KONSENSÜS ROZETİ:* {consensus_badges[0]}"

            is_super = any("SK" in b for b in consensus_badges)
            is_double = any("ÇAO" in b for b in consensus_badges)

            if is_manual:
                header = f"📢 *ANALİST TAKİP ALARMI*"
            elif is_super:
                header = f"🚀 *SÜPER KONSENSÜS ALARMI*"
            elif is_double:
                header = f"🔥 *ÇİFTE ALGO ONAY ALARMI*"
            else:
                header = f"⚡ *MODEL FIRSAT ALARMI*"

            entry_low = float(item['entry'][0])
            entry_high = float(item['entry'][1])
            raw_stop = float(item.get('stop') or (entry_low * 0.96))
            effective_stop = round(min(raw_stop, entry_low * 0.97), 2)
            if effective_stop >= entry_low:
                effective_stop = round(entry_low * 0.96, 2)

            targets = item.get("targets") or [item["price"], item["price"], item["price"]]
            tp1 = targets[0] if len(targets) > 0 else item["price"]
            tp2 = targets[1] if len(targets) > 1 else tp1
            tp3 = targets[2] if len(targets) > 2 else tp2

            message = (
                f"{header}\n\n"
                f"📌 *Hisse:* #{item['ticker']}\n"
                f"⭐ *Model Puanı:* {item['score']}\n"
                f"💬 *Açıklama:* {item.get('analystMessage') or item['strategy']}"
                f"{badge_info}\n\n"
                f"💵 *Güncel Fiyat:* {item['price']} TL\n"
                f"🎯 *Alım Bölgesi:* {entry_low}–{entry_high} TL arası\n"
                f"🛑 *Zarar Kes (Stop):* {effective_stop} TL (Altına düşerse satıp çıkılmalı)\n"
                f"🚀 *Kâr Hedefleri:*\n"
                f"  • *1. Hedef (TP1):* {tp1} TL\n"
                f"  • *2. Hedef (TP2):* {tp2} TL\n"
                f"  • *3. Hedef (TP3):* {tp3} TL"
            )
            delivered = _notify(message)
            _append_notification_log(item, message, delivered)
            if delivered:
                state[key] = True
                changed = True
        if changed:
            _save_state(state)

        # Analyst levels use the current quote overlay and must not wait for
        # the expensive technical model refresh. Oğuz alerts are the user's
        # primary channel, so check them before the lower-priority summaries.
        check_analyst_level_alerts(payload)
        _refresh_analyst_tracks(payload)
        tracks = _load_tracking()

        # Analyst-only mode: model summaries, commodity correlations and
        # paper-portfolio events are intentionally disabled.

        with _status_lock:
            _status.update({"running": True, "lastRun": datetime.now().astimezone().isoformat(timespec="seconds"), "lastError": None, "opportunities": opportunities, "tracking": list(tracks.values()), "notificationsEnabled": bool(os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()), "topic": os.getenv("NTFY_TOPIC", DEFAULT_NTFY_TOPIC).strip()})
        return opportunities
    except Exception as exc:
        with _status_lock:
            _status.update({"running": True, "lastRun": datetime.now().astimezone().isoformat(timespec="seconds"), "lastError": str(exc)})
        raise


def run_once() -> list[dict]:
    """Run one notification cycle; overlapping HTTP/background calls share one lock."""
    if not _run_lock.acquire(blocking=False):
        with _status_lock:
            return list(_status.get("opportunities") or [])
    try:
        return _run_once_unlocked()
    finally:
        _run_lock.release()


def worker_status() -> dict:
    with _status_lock:
        return dict(_status)


def notification_log(limit: int = 500, date: str | None = None) -> list[dict]:
    try:
        rows = json.loads(NOTIFICATION_LOG_PATH.read_text(encoding="utf-8")) if NOTIFICATION_LOG_PATH.exists() else []
        if not isinstance(rows, list):
            return []
        if date:
            rows = [row for row in rows if str(row.get("timestamp", "")).startswith(date)]
        return rows[: max(1, min(int(limit), 2000))]
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


def _start_or_update_analyst_track(
    *, ticker: str, name: str, source: str, alert_type: str,
    level: float, price: float, note: str, now: str,
) -> None:
    """Persist an analyst alert as a price-performance experiment."""
    tracks = _load_tracking()
    day = now[:10]
    key = f"analyst|{source}|{ticker}|{alert_type}|{float(level):.4f}|{day}"
    track = tracks.get(key)
    if not track:
        track = {
            "trackId": key,
            "ticker": ticker,
            "name": name,
            "strategy": "Analist Alarmı",
            "analystSource": source,
            "alarmType": alert_type,
            "alarmLevel": float(level),
            "alarmPrice": float(price),
            "analystMessage": note,
            "startedAt": now,
            "startPrice": float(price),
            "lastAt": now,
            "lastPrice": float(price),
            "highestPrice": float(price),
            "highestAt": now,
            "changePercent": 0.0,
            "maxChangePercent": 0.0,
            "updates": [],
            "closed": False,
        }
        tracks[key] = track
    _update_analyst_track(track, price, now)
    _save_tracking(tracks)


def _update_analyst_track(track: dict, price: float, now: str) -> None:
    price = float(price)
    track.setdefault("updates", []).append({"timestamp": now, "price": price})
    track["updates"] = track["updates"][-100:]
    track["lastAt"] = now
    track["lastPrice"] = price
    start = float(track.get("alarmPrice") or track.get("startPrice") or price)
    track["changePercent"] = round((price / start - 1) * 100, 2) if start else 0.0
    if price >= float(track.get("highestPrice") or price):
        track["highestPrice"] = price
        track["highestAt"] = now
    track["maxChangePercent"] = round((float(track.get("highestPrice") or price) / start - 1) * 100, 2) if start else 0.0


def _refresh_analyst_tracks(payload: dict) -> None:
    tracks = _load_tracking()
    prices = {}
    for stock in payload.get("stocks", []):
        quote = stock.get("delayedQuote") or {}
        value = quote.get("price") or stock.get("price")
        if value not in (None, ""):
            prices[str(stock.get("ticker")).upper()] = float(value)
    now = get_tr_now().isoformat(timespec="seconds")
    changed = False
    for track in tracks.values():
        if track.get("strategy") == "Analist Alarmı" and track.get("ticker", "").upper() in prices:
            _update_analyst_track(track, prices[track["ticker"].upper()], now)
            changed = True
    if changed:
        _save_tracking(tracks)


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
        if track.get("strategy") != "Analist Alarmı":
            _advance_trade_lifecycle(track, price, now)
        else:
            _update_analyst_track(track, price, now)
    _save_tracking(tracks)
    return tracks


if __name__ == "__main__":
    while True:
        try:
            print(json.dumps(run_once(), ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        time.sleep(INTERVAL_SECONDS)
