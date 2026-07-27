"""Walk-forward, daily paper-trading backtest for the decision-support model.

This module deliberately uses only data available on each signal day. It is
not an execution engine and does not promise future returns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

COMMISSION = 0.001
SLIPPAGE = 0.0005
HORIZON = 20


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))


def _cci(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    average = typical.rolling(period).mean()
    deviation = typical.rolling(period).apply(
        lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True
    )
    return (typical - average) / (0.015 * deviation.replace(0, np.nan))


def _smi(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    rolling_low = frame["Low"].rolling(14).min()
    rolling_high = frame["High"].rolling(14).max()
    distance = frame["Close"] - (rolling_high + rolling_low) / 2
    price_range = rolling_high - rolling_low
    smooth_distance = distance.ewm(span=3, adjust=False).mean().ewm(span=3, adjust=False).mean()
    smooth_range = price_range.ewm(span=3, adjust=False).mean().ewm(span=3, adjust=False).mean()
    smi = 200 * smooth_distance / smooth_range.replace(0, np.nan)
    return smi, smi.ewm(span=5, adjust=False).mean()


def _mfi(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    flow = typical * frame["Volume"]
    direction = typical.diff()
    positive = flow.where(direction > 0, 0.0).rolling(period).sum()
    negative = flow.where(direction < 0, 0.0).rolling(period).sum()
    ratio = positive / negative.replace(0, np.nan)
    return 100 - 100 / (1 + ratio)


def _connors_rsi(close: pd.Series) -> pd.Series:
    changes = close.diff()
    streak_values: list[float] = []
    streak = 0.0
    for change in changes:
        if pd.isna(change) or change == 0:
            streak = 0.0
        elif change > 0:
            streak = streak + 1 if streak > 0 else 1.0
        else:
            streak = streak - 1 if streak < 0 else -1.0
        streak_values.append(streak)
    streak_rsi = _rsi(pd.Series(streak_values, index=close.index), 2)
    percent_rank = close.pct_change().rolling(100).apply(
        lambda values: float(pd.Series(values).rank(pct=True).iloc[-1] * 100), raw=False
    )
    return (_rsi(close, 3) + streak_rsi + percent_rank) / 3


def _signals(frame: pd.DataFrame) -> pd.DataFrame:
    close, high, low, volume = frame["Close"], frame["High"], frame["Low"], frame["Volume"]
    ema5 = close.ewm(span=5, adjust=False).mean()
    ema8 = close.ewm(span=8, adjust=False).mean()
    ema13 = close.ewm(span=13, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    sma200 = close.rolling(200).mean()
    rsi = _rsi(close)
    cci = _cci(frame)
    smi, smi_signal = _smi(frame)
    mfi = _mfi(frame)
    crsi = _connors_rsi(close)
    atr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1).rolling(14).mean()
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index)
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr.replace(0, np.nan)
    adx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).ewm(alpha=1 / 14, adjust=False).mean()
    vol_ratio = volume / volume.rolling(20).mean()
    breakout = close > high.shift(1).rolling(20).max()
    stochastic_k = 100 * (close - low.rolling(14).min()) / (high.rolling(14).max() - low.rolling(14).min()).replace(0, np.nan)
    stochastic_d = stochastic_k.rolling(3).mean()
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_hist = macd - macd.ewm(span=9, adjust=False).mean()
    recent_drawdown = close / close.rolling(60).max() - 1
    return pd.DataFrame({"open": frame["Open"], "close": close, "high": high, "low": low, "volume": volume, "ema5": ema5, "ema8": ema8, "ema13": ema13, "ema20": ema20, "ema50": ema50, "sma200": sma200, "rsi": rsi, "cci": cci, "smi": smi, "smi_signal": smi_signal, "mfi": mfi, "crsi": crsi, "atr": atr, "adx": adx, "plus_di": plus_di, "minus_di": minus_di, "vol_ratio": vol_ratio, "breakout": breakout, "stochastic_k": stochastic_k, "stochastic_d": stochastic_d, "macd_hist": macd_hist, "recent_drawdown": recent_drawdown}).dropna()


def _simulate(s: pd.DataFrame, i: int, entry: float, stop: float, target: float) -> tuple[float, str, int]:
    # The position opens at this session's Open, so the same session's High/Low
    # must be evaluated. If both levels occur in the same daily candle, use the
    # conservative assumption and count the stop first.
    end = min(i + HORIZON - 1, len(s) - 1)
    for j in range(i, end + 1):
        session_open = float(s.iloc[j].open)
        if session_open <= stop:
            return (session_open / entry - 1 - COMMISSION - SLIPPAGE), "STOP", j - i + 1
        if s.iloc[j].low <= stop:
            return (stop / entry - 1 - COMMISSION - SLIPPAGE), "STOP", j - i + 1
        if s.iloc[j].high >= target:
            return (target / entry - 1 - COMMISSION - SLIPPAGE), "TARGET", j - i + 1
    exit_price = float(s.iloc[end].close)
    return (exit_price / entry - 1 - COMMISSION - SLIPPAGE), "TIME", end - i + 1


def backtest_ticker(ticker: str, start: str = "2020-01-01") -> dict[str, Any]:
    symbol = ticker if ticker.endswith(".IS") else f"{ticker}.IS"
    requested_start = pd.Timestamp(start).tz_localize(None)
    warmup_start = (requested_start - pd.Timedelta(days=400)).date().isoformat()
    raw = yf.download(symbol, start=warmup_start, auto_adjust=False, progress=False, threads=False)
    if raw.empty:
        return {"ticker": ticker.removesuffix(".IS"), "error": "Tarihçe bulunamadı"}
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    s = _signals(raw)
    positive_reversal = (s.close > s.open) & (s.close > s.close.shift(1))
    smi_cross = (s.smi > s.smi_signal) & (s.smi.shift(1) <= s.smi_signal.shift(1))
    stochastic_cross = (s.stochastic_k > s.stochastic_d) & (s.stochastic_k.shift(1) <= s.stochastic_d.shift(1))
    prior_10_low = s.low.shift(1).rolling(10).min()
    range_size = (s.high - s.low).replace(0, np.nan)
    lower_wick = (pd.concat([s.open, s.close], axis=1).min(axis=1) - s.low) / range_size
    liquidity_sweep = (s.low < prior_10_low) & (s.close > prior_10_low) & (lower_wick >= 0.30)
    trend_stack = (s.close > s.ema20) & (s.ema20 > s.ema50) & (s.ema50 > s.sma200)
    pullback_distance = (s.close / s.ema20 - 1).abs()
    recent_volume = s.volume.rolling(5).mean()
    earlier_volume = s.volume.shift(5).rolling(15).mean()
    vcp_proxy = recent_volume < earlier_volume

    tactics = {
        "Dipten Dönüş": smi_cross & (s.rsi <= 52) & (s.cci <= 25) & ((s.close / s.ema20 - 1) <= 0.04),
        "Derin Dönüş": (s.recent_drawdown <= -0.10) & (pd.concat([s.smi, s.smi.shift(1)], axis=1).min(axis=1) <= -25) & stochastic_cross & (s.rsi <= 48) & positive_reversal & (s.vol_ratio >= 0.65),
        "Uzun Vade": trend_stack & s.rsi.between(45, 72) & (s.adx >= 18),
        "Momentum Kırılımı": s.breakout & (s.vol_ratio >= 1.15) & (s.macd_hist > 0) & (s.macd_hist >= s.macd_hist.shift(1)) & s.rsi.between(52, 79) & (s.plus_di > s.minus_di),
        "CRSI Scalp": (s.crsi <= 25) & (s.rsi <= 48) & (s.close <= s.ema20),
        "Chartist MM Trend": trend_stack & (s.adx >= 22) & (s.plus_di > s.minus_di) & (s.macd_hist > 0) & vcp_proxy,
        "Wyckoff Spring": liquidity_sweep & positive_reversal & (s.vol_ratio >= 0.75),
        "Money Dip": ((s.close / s.close.shift(5) - 1) < 0) & (s.mfi >= 52) & (s.mfi > s.mfi.shift(5)) & (s.close > s.ema50) & ((s.close / s.ema20 - 1) >= -0.06) & (s.vol_ratio >= 0.65),
        "Chartist Trender": (s.close > s.ema50) & (pullback_distance <= 0.04) & positive_reversal & (s.plus_di > s.minus_di) & (s.macd_hist >= s.macd_hist.shift(1)),
    }

    # Dynamic multi-algorithm consensus backtesting (ÇAO & SK)
    n_matches = sum(mask.fillna(False).astype(int) for mask in tactics.values())
    tactics["Çifte Algo Onayı (ÇAO)"] = (n_matches == 2)
    tactics["Süper Konsensüs (SK3+)"] = (n_matches >= 3)
    output = []
    for name, mask in tactics.items():
        trades = []
        last_signal = -HORIZON
        eligible_mask = mask.fillna(False) & (s.index.tz_localize(None) >= requested_start)
        for i in np.flatnonzero(eligible_mask.to_numpy()):
            if i - last_signal < 5 or i + 1 >= len(s):
                continue
            entry = float(s.iloc[i + 1].open if "open" in s.columns else s.iloc[i + 1].close)
            atr = float(s.iloc[i].atr)
            if not np.isfinite(entry) or not np.isfinite(atr) or atr <= 0:
                continue
            ret, outcome, days = _simulate(s, i + 1, entry * (1 + SLIPPAGE), entry - 1.5 * atr, entry + 2.0 * atr)
            trades.append({"date": str(s.index[i + 1].date()), "signalDate": str(s.index[i].date()), "entryDate": str(s.index[i + 1].date()), "return": round(float(ret * 100), 3), "outcome": outcome, "days": int(days)})
            # Do not open a second position while the previous simulated trade is open.
            last_signal = i + int(days)
        returns = [trade["return"] for trade in trades]
        equity = np.cumprod([1 + value / 100 for value in returns]) if returns else np.array([])
        equity_with_origin = np.concatenate(([1.0], equity)) if len(equity) else np.array([])
        drawdown = float(np.min(equity_with_origin / np.maximum.accumulate(equity_with_origin) - 1) * 100) if len(equity_with_origin) else 0.0
        positive_count = sum(t["return"] > 0 for t in trades)
        target_hits = sum(t["outcome"] == "TARGET" for t in trades)
        stop_hits = sum(t["outcome"] == "STOP" for t in trades)
        output.append({"tactic": name, "trades": len(trades), "wins": positive_count, "winRate": round(positive_count / len(trades) * 100, 2) if trades else None, "positiveRate": round(positive_count / len(trades) * 100, 2) if trades else None, "targetHits": target_hits, "targetHitRate": round(target_hits / len(trades) * 100, 2) if trades else None, "stopHits": stop_hits, "stopRate": round(stop_hits / len(trades) * 100, 2) if trades else None, "avgReturn": round(float(np.mean(returns)), 3) if returns else None, "totalReturn": round(float((equity[-1] - 1) * 100), 2) if len(equity) else None, "maxDrawdown": round(drawdown, 2), "sample": trades[-10:]})
    return {
        "ticker": ticker.removesuffix(".IS"),
        "from": str(max(s.index[0].tz_localize(None), requested_start).date()),
        "to": str(s.index[-1].date()),
        "requestedFrom": start,
        "commission": COMMISSION,
        "slippage": SLIPPAGE,
        "scope": "nine-independent-algorithms-not-model-score",
        "warnings": [
            "Bu sonuçlar pozisyon puanını değil dokuz bağımsız teknik algoritmayı test eder.",
            "Money Dip gerçek takas verisi yerine MFI ve hacim vekili kullanır.",
            "Güncel BIST100 bileşenleri geçmişe uygulandığı için bileşen kalıcılığı yanlılığı içerir.",
            "Günlük mumlarda aynı seans içinde stop ve hedef sırası bilinemez; stop önce varsayılır.",
        ],
        "tactics": output,
    }


if __name__ == "__main__":
    import json, sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "ASELS"
    print(json.dumps(backtest_ticker(ticker), ensure_ascii=False, indent=2))
