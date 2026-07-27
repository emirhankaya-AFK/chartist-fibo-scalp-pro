from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


@dataclass
class RiskPolicy:
    max_risk_per_trade: float = 0.01
    max_open_positions: int = 8
    max_sector_exposure: float = 0.25
    commission: float = 0.001
    slippage: float = 0.0005


def position_plan(capital: float, price: float, stop: float, policy: RiskPolicy | None = None) -> dict[str, Any]:
    policy = policy or RiskPolicy()
    if capital <= 0 or price <= 0 or stop <= 0 or stop >= price:
        return {"allowed": False, "reason": "Geçersiz sermaye/fiyat/stop"}
    risk_per_share = price - stop
    max_loss = capital * policy.max_risk_per_trade
    lots = int(max_loss // risk_per_share)
    used = lots * price * (1 + policy.commission + policy.slippage)
    return {"allowed": lots > 0 and used <= capital, "lots": lots, "usedCapital": round(used, 2), "maxLoss": round(lots * risk_per_share, 2), "riskPercent": round((lots * risk_per_share / capital) * 100, 3), "policy": asdict(policy)}


def portfolio_snapshot(positions: list[dict[str, Any]], prices: dict[str, float], starting_cash: float) -> dict[str, Any]:
    value = float(starting_cash)
    rows = []
    for position in positions:
        ticker = position.get("ticker")
        lots = int(position.get("lots", 0))
        entry = float(position.get("entryPrice", 0))
        current = float(prices.get(ticker, entry))
        pnl = (current - entry) * lots
        value += current * lots
        rows.append({"ticker": ticker, "lots": lots, "entryPrice": entry, "currentPrice": current, "pnl": round(pnl, 2)})
    return {"startingCash": starting_cash, "marketValue": round(value, 2), "pnl": round(sum(row["pnl"] for row in rows), 2), "positions": rows, "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds")}
