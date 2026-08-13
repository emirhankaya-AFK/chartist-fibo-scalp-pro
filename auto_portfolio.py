from __future__ import annotations
import json
import os
import math

PORTFOLIO_FILE = "data/auto_portfolio.json"

def send_auto_notification(
    message: str,
    *,
    ticker: str | None = None,
    event_type: str | None = None,
) -> bool:
    """Send a paper-portfolio push through the shared, audited delivery path."""
    from intraday_opportunity_worker import send_audited_notification

    return send_audited_notification(
        message,
        category="auto-portfolio",
        ticker=ticker or "SANAL PORTFÖY",
        context={"trigger": "paper_portfolio_event", "eventType": event_type},
    )


def load_portfolio() -> dict:
    if not os.path.exists(PORTFOLIO_FILE):
        os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
        state = {
            "initial_capital": 10000.0,
            "current_cash": 10000.0,
            "last_updated_date": "",
            "positions": [],
            "history": []
        }
        save_portfolio(state)
        return state
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            if "positions" not in state: state["positions"] = []
            if "history" not in state: state["history"] = []
            if "current_cash" not in state: state["current_cash"] = state.get("initial_capital", 10000.0)
            return state
    except Exception:
        return {
            "initial_capital": 10000.0,
            "current_cash": 10000.0,
            "last_updated_date": "",
            "positions": [],
            "history": []
        }

def save_portfolio(state: dict):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def reset_portfolio() -> dict:
    state = {
        "initial_capital": 10000.0,
        "current_cash": 10000.0,
        "last_updated_date": "",
        "positions": [],
        "history": []
    }
    save_portfolio(state)
    send_auto_notification(
        "↻ *Robot Portföy Sıfırlandı:* Başlangıç bakiyesi 10.000 TL olarak yenilendi.",
        event_type="RESET",
    )
    return state

def update_auto_portfolio(stocks: list[dict], data_date_str: str) -> dict:
    """
    Executes automated paper trading logic:
    1. Checks active positions against current daily high/low for exit conditions:
       - Stop Loss (100% exit at stop price)
       - TP1 (Scale out 50% at TP1 target)
       - TP2 (Exit remaining 50% at TP2 target)
    2. Opens new positions for stocks with modelScore >= 80 if cash is available
       (Max 5 concurrent positions, 2,000 TL allocated per trade).
    3. Triggers Telegram / NTFY push notifications on trades.
    """
    state = load_portfolio()
    stocks_map = {s["ticker"]: s for s in stocks}
    
    # Update current prices in active positions
    for pos in state["positions"]:
        ticker = pos["ticker"]
        if ticker in stocks_map:
            pos["current_price"] = stocks_map[ticker]["price"]
            pos["model_score"] = stocks_map[ticker]["modelScore"]
            
    # Process exits for active positions
    active_positions = []
    for pos in state["positions"]:
        ticker = pos["ticker"]
        if ticker not in stocks_map:
            active_positions.append(pos)
            continue
            
        stock = stocks_map[ticker]
        ohlc = stock.get("officialOhlc") or {}
        low = ohlc.get("low", stock["price"])
        high = ohlc.get("high", stock["price"])
        
        # Check Stop Loss first (conservative exit order)
        if low <= pos["stop_price"]:
            exit_price = pos["stop_price"]
            pnl = (exit_price - pos["entry_price"]) * pos["qty"]
            ret_pct = (exit_price / pos["entry_price"] - 1) * 100
            state["current_cash"] += exit_price * pos["qty"]
            state["history"].append({
                "ticker": ticker,
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "entry_date": pos["entry_date"],
                "exit_date": data_date_str,
                "pnl": round(pnl, 2),
                "outcome": "STOP",
                "return_percent": round(ret_pct, 2)
            })
            send_auto_notification(
                f"🚨 *AUTO-TRADE STOP OLDU*\n\n"
                f"📌 *Hisse:* #{ticker}\n"
                f"💵 *Çıkış Fiyatı:* {exit_price} TL\n"
                f"📉 *Net K/Z:* {pnl:+.2f} TL (%{ret_pct:+.2f})",
                ticker=ticker,
                event_type="STOP",
            )
            continue
            
        # Check TP1 (Scale out 50% of the position)
        if not pos.get("tp1_hit", False) and high >= pos["tp1"]:
            sell_qty = math.floor(pos["qty"] / 2)
            if sell_qty > 0:
                pos["qty"] -= sell_qty
                pos["cost"] = pos["qty"] * pos["entry_price"]
                exit_price = pos["tp1"]
                pnl = (exit_price - pos["entry_price"]) * sell_qty
                ret_pct = (exit_price / pos["entry_price"] - 1) * 100
                state["current_cash"] += exit_price * sell_qty
                state["history"].append({
                    "ticker": ticker,
                    "qty": sell_qty,
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "entry_date": pos["entry_date"],
                    "exit_date": data_date_str,
                    "pnl": round(pnl, 2),
                    "outcome": "TP1",
                    "return_percent": round(ret_pct, 2)
                })
                send_auto_notification(
                    f"🎯 *AUTO-TRADE TP1 HEDEFİ GÖRÜLDÜ (%50 KÂR ALIS)*\n\n"
                    f"📌 *Hisse:* #{ticker}\n"
                    f"💵 *Satış Fiyatı:* {exit_price} TL ({sell_qty} Lot)\n"
                    f"📈 *Kâr:* {pnl:+.2f} TL (%{ret_pct:+.2f})",
                    ticker=ticker,
                    event_type="TP1",
                )
            pos["tp1_hit"] = True
            
        # Check TP2 (Exit remaining portion of position)
        if high >= pos["tp2"]:
            exit_price = pos["tp2"]
            pnl = (exit_price - pos["entry_price"]) * pos["qty"]
            ret_pct = (exit_price / pos["entry_price"] - 1) * 100
            state["current_cash"] += exit_price * pos["qty"]
            state["history"].append({
                "ticker": ticker,
                "qty": pos["qty"],
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "entry_date": pos["entry_date"],
                "exit_date": data_date_str,
                "pnl": round(pnl, 2),
                "outcome": "TP2",
                "return_percent": round(ret_pct, 2)
            })
            send_auto_notification(
                f"🚀 *AUTO-TRADE TP2 ANA HEDEF GÖRÜLDÜ (KAPANDI)*\n\n"
                f"📌 *Hisse:* #{ticker}\n"
                f"💵 *Çıkış Fiyatı:* {exit_price} TL ({pos['qty']} Lot)\n"
                f"📈 *Net K/Z:* {pnl:+.2f} TL (%{ret_pct:+.2f})",
                ticker=ticker,
                event_type="TP2",
            )
            continue
            
        active_positions.append(pos)
        
    state["positions"] = active_positions
    
    # Only enter high-conviction, risk-filtered OPEN signals. There is no
    # fallback to WATCH/uncertain stocks: an empty candidate list is safer
    # than filling the paper portfolio with noise.
    def eligible_entry(stock: dict) -> bool:
        score = float(stock.get("modelScore") or 0)
        technical = float(stock.get("technicalScore") or stock.get("componentScores", {}).get("technical") or 0)
        stop_score = float(stock.get("componentScores", {}).get("stop") or 0)
        rr = float(stock.get("rr") or 0)
        badges = [str(b).upper() for b in (stock.get("badges") or [])]
        has_risk_badge = any("RİSK" in badge or "RISK" in badge or "OBO" in badge for badge in badges)
        return (
            stock.get("recommendation") == "OPEN"
            and score >= 82
            and technical >= 65
            and stop_score >= 60
            and rr >= 1.8
            and not has_risk_badge
        )

    candidates = [s for s in stocks if eligible_entry(s)]
    candidates.sort(key=lambda s: s.get("modelScore", 0), reverse=True)

    for stock in candidates:
        if len(state["positions"]) >= 5:
            break

        ticker = stock["ticker"]
        already_owned = any(p["ticker"] == ticker for p in state["positions"])
        if already_owned:
            continue

        allocation = min(2000.0, state["current_cash"])
        if state["current_cash"] >= 500.0:  # If at least 500 TL cash left
            entry_price = float(stock["price"])
            if entry_price <= 0:
                continue
            qty = math.floor(allocation / entry_price)
            if qty > 0:
                cost = qty * entry_price
                state["current_cash"] -= cost
                targets = stock.get("targets") or [entry_price * 1.05, entry_price * 1.10, entry_price * 1.15]
                stop_price = stock.get("stop") or round(entry_price * 0.95, 2)

                state["positions"].append({
                    "ticker": ticker,
                    "qty": qty,
                    "entry_price": entry_price,
                    "current_price": entry_price,
                    "entry_date": data_date_str,
                    "stop_price": stop_price,
                    "tp1": targets[0],
                    "tp2": targets[1] if len(targets) > 1 else targets[0],
                    "tp3": targets[2] if len(targets) > 2 else targets[-1],
                    "tp1_hit": False,
                    "cost": cost,
                    "model_score": stock["modelScore"]
                })
                send_auto_notification(
                    f"🤖 *SANAL PORTFÖY ALIM YAPTI*\n\n"
                    f"📌 *Hisse:* #{ticker}\n"
                    f"⭐ *Model Puanı:* {stock['modelScore']}\n"
                    f"💵 *Alış Fiyatı:* {entry_price:.2f} TL ({qty} Lot)\n"
                    f"💰 *Harcanan:* {cost:,.2f} TL\n\n"
                    f"🎯 *Kâr & Stop Hedefleri:*\n"
                    f"  • Zarar Kes (Stop): {stop_price:.2f} TL\n"
                    f"  • 1. Hedef (TP1): {targets[0]:.2f} TL\n"
                    f"  • 2. Hedef (TP2): {targets[1]:.2f} TL\n"
                    f"  • 3. Hedef (TP3): {targets[2]:.2f} TL\n\n"
                    f"💼 *Kalan Boştaki Nakit:* {state['current_cash']:,.2f} TL",
                    ticker=ticker,
                    event_type="BUY",
                )
                    
    state["last_updated_date"] = data_date_str
    save_portfolio(state)
    return state
