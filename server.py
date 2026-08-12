from __future__ import annotations

from flask import Flask, jsonify, send_from_directory, Response, request
from datetime import datetime
from functools import lru_cache
import os
import threading
import time

from market_scanner import (
    scan_market,
    intraday_commodity_snapshots,
    _download_delayed_quotes,
    _load_excel_notes,
    _json_safe,
)
from commodity_groups import all_group_tickers, build_commodity_group_snapshot
from backtest import backtest_ticker
from analyst_benchmark import load_analyst_alerts
from intraday_opportunity_worker import run_once as run_opportunity_scan, worker_status, notification_log, tracking_log, add_manual_tracking, manual_tracking


app = Flask(__name__, static_folder=None)
_commodity_group_cache_lock = threading.Lock()
_commodity_group_cache = {"createdAt": 0.0, "payload": None}
COMMODITY_GROUP_CACHE_SECONDS = 240
_full_scan_lock = threading.Lock()
_full_scan_status = {
    "running": False,
    "startedAt": None,
    "finishedAt": None,
    "lastError": None,
    "dataDate": None,
}


def trigger_full_scan_async() -> bool:
    """Refresh the expensive technical model off-request so Render cannot time it out."""
    if not _full_scan_lock.acquire(blocking=False):
        return False

    def _refresh() -> None:
        _full_scan_status.update({
            "running": True,
            "startedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "lastError": None,
        })
        try:
            result = scan_market(force=True)
            _full_scan_status["dataDate"] = result.get("dataDate")
        except Exception as exc:
            _full_scan_status["lastError"] = f"{type(exc).__name__}: {exc}"
            print(f"[FULL SCAN ERROR] {type(exc).__name__}: {exc}")
        finally:
            _full_scan_status.update({
                "running": False,
                "finishedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
            _full_scan_lock.release()

    threading.Thread(target=_refresh, name="full-market-refresh", daemon=True).start()
    return True


@lru_cache(maxsize=256)
def _cached_backtest(ticker: str):
    return backtest_ticker(ticker)


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/app.js")
def app_javascript():
    return send_from_directory(".", "app.js")


@app.get("/styles.css")
def app_styles():
    return send_from_directory(".", "styles.css")


@app.get("/favicon.ico")
def favicon():
    return Response(status=204)


@app.get("/api/scan")
def api_scan():
    try:
        payload = _json_safe(scan_market())
        if payload.get("staleData"):
            trigger_full_scan_async()
        payload["fullScanRefresh"] = dict(_full_scan_status)
        return jsonify(payload)
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
                "safeMode": True,
                "stocks": [],
            }
        ), 503


@app.get("/api/scan/refresh")
def api_scan_refresh():
    started = trigger_full_scan_async()
    payload = _json_safe(scan_market())
    payload["refreshAccepted"] = started
    payload["fullScanRefresh"] = dict(_full_scan_status)
    return jsonify(payload), 202 if started else 200


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "status": "ok",
            "serverTime": datetime.now().astimezone().isoformat(timespec="seconds"),
            "pricePolicy": "official-bist-close-required",
            "unverifiedRecommendations": False,
            "orderExecution": "disabled",
            "safety": "Sinyaller yalnızca karar desteğidir; otomatik emir gönderilmez.",
            "fullScanRefresh": dict(_full_scan_status),
        }
    )


@app.get("/api/market-wind")
def api_market_wind():
    try:
        scan_data = scan_market()
        wind_report = scan_data.get("marketWind")
        if not wind_report:
            from market_scanner import _download_history, BENCHMARK, build_market_wind_report
            df = _download_history([BENCHMARK])[BENCHMARK]
            wind_report = build_market_wind_report(df)
        return jsonify(wind_report)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


@app.get("/api/commodity-groups")
def api_commodity_groups():
    """Visible gold, silver, copper and Brent relationship groups."""
    now = time.time()
    force = str(request.args.get("refresh", "")).lower() in {"1", "true", "yes"}
    with _commodity_group_cache_lock:
        cached = _commodity_group_cache.get("payload")
        created_at = float(_commodity_group_cache.get("createdAt") or 0.0)
        if cached and not force and now - created_at < COMMODITY_GROUP_CACHE_SECONDS:
            return jsonify(cached)

    try:
        scan_payload = dict(scan_market())
        commodity_rows = intraday_commodity_snapshots(force=force)
        symbols = [f"{ticker}.IS" for ticker in all_group_tickers()]
        delayed_quotes = _download_delayed_quotes(symbols)
        payload = _json_safe(
            build_commodity_group_snapshot(scan_payload, commodity_rows, delayed_quotes)
        )
        with _commodity_group_cache_lock:
            _commodity_group_cache["createdAt"] = now
            _commodity_group_cache["payload"] = payload
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "groups": []}), 503


@app.get("/api/analyst-alerts")
def api_analyst_alerts():
    """External analyst levels and triggered history, kept separate from model signals."""
    try:
        return jsonify(load_analyst_alerts())
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "alerts": [], "history": [], "summary": {}}), 503


@app.get("/api/opportunities")
def api_opportunities():
    return jsonify({"status": "ok", **worker_status()})


@app.get("/api/analyst-notes")
def api_analyst_notes():
    try:
        notes_by_ticker = _load_excel_notes()
        rows = []
        for ticker, notes in notes_by_ticker.items():
            for note in notes:
                rows.append({
                    "ticker": ticker,
                    "source": note.get("source", "Kullanıcı Excel'i"),
                    "sheet": note.get("sheet"),
                    "support": note.get("Destek Seviyesi (TL)"),
                    "resistance": note.get("Direnç Seviyesi (TL)"),
                    "target": note.get("Hedef Fiyat / Oran"),
                    "instruction": note.get("Alarm Açıklaması / Talimatı"),
                    "text": note.get("Özel Açıklamalar / Analiz Notları"),
                })
        sources = {}
        for row in rows:
            sources[row["source"]] = sources.get(row["source"], 0) + 1
        return jsonify({"status": "ok", "rows": rows, "summary": {"notes": len(rows), "tickers": len(notes_by_ticker), "sources": sources}})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc), "rows": [], "summary": {}}), 503


@app.get("/api/notifications")
def api_notifications():
    try:
        limit = int(request.args.get("limit", "500"))
    except (TypeError, ValueError):
        limit = 500
    date = str(request.args.get("date", "")).strip() or None
    return jsonify({
        "status": "ok",
        "notifications": notification_log(limit=limit, date=date),
        "tracking": tracking_log(),
        "worker": worker_status(),
        "filters": {"date": date, "limit": max(1, min(limit, 2000))},
    })


@app.post("/api/tracking/manual")
def api_manual_tracking():
    body = request.get_json(silent=True) or {}
    ticker = str(body.get("ticker", "")).strip()
    if not ticker.isalnum() or len(ticker) > 12:
        return jsonify({"status": "error", "message": "Geçersiz hisse kodu"}), 400
    return jsonify({"status": "ok", "ticker": ticker.upper(), "tracking": add_manual_tracking(ticker)})


_worker_enabled = os.getenv("ENABLE_OPPORTUNITY_WORKER", "1").strip().lower() not in {"0", "false", "no"}


@app.post("/api/worker/toggle")
def api_worker_toggle():
    global _worker_enabled
    _worker_enabled = not _worker_enabled
    status = worker_status()
    status["enabled"] = _worker_enabled
    return jsonify({"status": "ok", "workerEnabled": _worker_enabled, "worker": status})


def _opportunity_loop():
    interval = max(30, int(os.getenv("OPPORTUNITY_INTERVAL_SECONDS", "60")))
    while True:
        if _worker_enabled:
            try:
                run_opportunity_scan()
            except Exception as exc:
                print(f"[OPPORTUNITY WORKER ERROR] {type(exc).__name__}: {exc}")
        time.sleep(interval)


def _keep_alive_loop():
    """Internal & External keep-alive pinger to ensure Render container remains 100% awake."""
    import urllib.request
    render_url = "https://chartist-fibo-scalp-pro.onrender.com/api/notifications"
    local_port = os.getenv("PORT", "8080")
    local_url = f"http://127.0.0.1:{local_port}/api/notifications"
    while True:
        time.sleep(180)  # Ping every 3 minutes
        for url in [local_url, render_url]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "KeepAlivePinger/1.0"})
                with urllib.request.urlopen(req, timeout=15):
                    pass
            except Exception as exc:
                print(f"[KEEP ALIVE ERROR] {url}: {type(exc).__name__}: {exc}")


@app.get("/api/backtest/<ticker>")
def api_backtest(ticker: str):
    clean = ticker.upper().replace(".IS", "")
    if not clean.isalnum() or len(clean) > 12:
        return jsonify({"status": "error", "message": "Geçersiz hisse kodu"}), 400
    try:
        result = _cached_backtest(clean)
        if result.get("error") or not isinstance(result.get("tactics"), list):
            return jsonify({"status": "error", "message": result.get("error", "Backtest üretilemedi")}), 404
        return jsonify({"status": "ok", "result": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


_scan_lock = threading.Lock()

def trigger_scan_async():
    """Triggers market scan and notification dispatch in background if not already running."""
    if _scan_lock.acquire(blocking=False):
        def _worker():
            try:
                run_opportunity_scan()
            except Exception as exc:
                print(f"[ASYNC SCAN ERROR] {type(exc).__name__}: {exc}")
            finally:
                _scan_lock.release()
        threading.Thread(target=_worker, daemon=True).start()


@app.get("/api/auto-portfolio")
def api_auto_portfolio():
    try:
        from auto_portfolio import load_portfolio
        return jsonify({"status": "ok", "portfolio": load_portfolio()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


@app.post("/api/auto-portfolio/reset")
def api_auto_portfolio_reset():
    try:
        from auto_portfolio import reset_portfolio
        return jsonify({"status": "ok", "portfolio": reset_portfolio()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503


_threads_started = False

def _ensure_threads():
    global _threads_started
    if _threads_started:
        return
    _threads_started = True
    threading.Thread(target=_opportunity_loop, name="opportunity-worker", daemon=True).start()
    threading.Thread(target=_keep_alive_loop, name="keep-alive-worker", daemon=True).start()


_ensure_threads()


@app.before_request
def _before_request_hook():
    _ensure_threads()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
