from __future__ import annotations

from flask import Flask, jsonify, send_from_directory, Response, request
from datetime import datetime
from functools import lru_cache
import os
import threading
import time

from market_scanner import scan_market, _load_excel_notes, _json_safe
from backtest import backtest_ticker
from analyst_benchmark import load_analyst_alerts
from intraday_opportunity_worker import run_once as run_opportunity_scan, worker_status, notification_log, tracking_log, add_manual_tracking, manual_tracking


app = Flask(__name__, static_folder=None)


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
        return jsonify(_json_safe(scan_market()))
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
    try:
        return jsonify(_json_safe(scan_market(force=True)))
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
                "safeMode": True,
                "stocks": [],
            }
        ), 503


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
    return jsonify({"status": "ok", "notifications": notification_log(), "tracking": tracking_log(), "worker": worker_status()})


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
    interval = max(60, int(os.getenv("OPPORTUNITY_INTERVAL_SECONDS", "300")))
    while True:
        if _worker_enabled:
            try:
                run_opportunity_scan()
            except Exception:
                pass
        time.sleep(interval)


def _keep_alive_loop():
    """Internal keep-alive self pinger to ensure Flask process remains active."""
    import urllib.request
    port = os.getenv("PORT", "8080")
    url = f"http://127.0.0.1:{port}/api/auto-portfolio"
    while True:
        time.sleep(240)  # Ping every 4 minutes
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KeepAlivePinger/1.0"})
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            pass


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


if _worker_enabled:
    threading.Thread(target=_opportunity_loop, name="opportunity-worker", daemon=True).start()
    threading.Thread(target=_keep_alive_loop, name="keep-alive-worker", daemon=True).start()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)

