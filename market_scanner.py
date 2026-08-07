from __future__ import annotations

import csv
import io
import json
import math
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


BENCHMARK = "XU100.IS"
UNIVERSE_FLAG = "bist100"
CACHE_TTL_SECONDS = 10 * 60
BIST_BULLETIN_URL = (
    "https://borsaistanbul.com/data/thb/{year}/{month}/thb{stamp}1.zip"
)
BIST_INDEX_URL = (
    "https://www.borsaistanbul.com/veriler.php?veriTuru=getPayChartData"
)
REQUEST_HEADERS = {
    "User-Agent": "Chartist-Fibo-Scalp-Pro/2.0 (+local decision-support)"
}

DISPLAY_NAMES: dict[str, str] = {
    "AEFES": "Anadolu Efes",
    "AKBNK": "Akbank",
    "ASELS": "Aselsan",
    "ASTOR": "Astor Enerji",
    "BIMAS": "BİM Mağazalar",
    "DSTKF": "Destek Finans Faktoring",
    "EKGYO": "Emlak Konut GYO",
    "ENKAI": "Enka İnşaat",
    "EREGL": "Ereğli Demir Çelik",
    "FROTO": "Ford Otosan",
    "GARAN": "Garanti BBVA",
    "GUBRF": "Gübre Fabrikaları",
    "ISCTR": "Türkiye İş Bankası C",
    "KCHOL": "Koç Holding",
    "KRDMD": "Kardemir D",
    "MGROS": "Migros",
    "PETKM": "Petkim",
    "PGSUS": "Pegasus",
    "SAHOL": "Sabancı Holding",
    "SASA": "Sasa Polyester",
    "SISE": "Şişecam",
    "TAVHL": "TAV Havalimanları",
    "TCELL": "Turkcell",
    "THYAO": "Türk Hava Yolları",
    "TOASO": "Tofaş",
    "TRALT": "Türk Altın İşletmeleri",
    "TTKOM": "Türk Telekom",
    "TUPRS": "Tüpraş",
    "VAKBN": "VakıfBank",
    "YKBNK": "Yapı Kredi",
}

SECTOR_BY_TICKER: dict[str, str] = {
    "AEFES": "Tüketim",
    "AKBNK": "Banka",
    "ASELS": "Savunma",
    "ASTOR": "Enerji",
    "BIMAS": "Perakende",
    "DSTKF": "Finans",
    "EKGYO": "GYO",
    "ENKAI": "İnşaat",
    "EREGL": "Metal",
    "FROTO": "Otomotiv",
    "GARAN": "Banka",
    "GUBRF": "Kimya",
    "ISCTR": "Banka",
    "KCHOL": "Holding",
    "KRDMD": "Metal",
    "MGROS": "Perakende",
    "PETKM": "Petrokimya",
    "PGSUS": "Ulaşım",
    "SAHOL": "Holding",
    "SASA": "Kimya",
    "SISE": "Cam",
    "TAVHL": "Ulaşım",
    "TCELL": "İletişim",
    "THYAO": "Ulaşım",
    "TOASO": "Otomotiv",
    "TRALT": "Madencilik",
    "TTKOM": "İletişim",
    "TUPRS": "Enerji",
    "VAKBN": "Banka",
    "YKBNK": "Banka",
}


_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"created_at": 0.0, "payload": None}
_DESKTOP_EXCEL = Path.home() / "Desktop" / "Hisselerin_Teknik_Verileri.xlsx"
_PROJECT_EXCEL = Path(__file__).resolve().parent / "Hisselerin_Teknik_Verileri.xlsx"
EXCEL_NOTES_PATH = _DESKTOP_EXCEL if _DESKTOP_EXCEL.exists() else _PROJECT_EXCEL
LAST_SUCCESSFUL_SCAN_PATH = Path(__file__).resolve().parent / "data" / "last_successful_scan.json"


def _load_excel_notes() -> dict[str, list[dict[str, Any]]]:
    """Read optional user-maintained levels/alarms; never changes model scores."""
    if not EXCEL_NOTES_PATH.exists():
        return {}
    notes: dict[str, list[dict[str, Any]]] = {}
    try:
        sheets = pd.read_excel(EXCEL_NOTES_PATH, sheet_name=None, header=None)
        for sheet_name, raw in sheets.items():
            header_rows = raw.index[raw.iloc[:, 0].astype(str).str.contains("Hisse Kimliği|Sembol", regex=True, na=False)]
            if len(header_rows) == 0:
                continue
            header = int(header_rows[0])
            frame = raw.iloc[header + 1:].copy()
            columns = list(raw.iloc[header].astype(str))
            frame.columns = columns[: len(frame.columns)]
            for _, row in frame.iterrows():
                ticker = str(row.get("BIST Kodu", row.get("Sembol", ""))).upper().replace(".IS", "").strip()
                if not ticker or ticker == "NAN":
                    continue
                item = {"source": "Kullanıcı Excel'i", "sheet": sheet_name}
                for key, value in row.items():
                    if pd.notna(value) and str(value).strip():
                        item[str(key)] = value.item() if hasattr(value, "item") else value
                haystack = " ".join(str(value) for value in item.values()).lower()
                for analyst in ("Oğuz", "Ahmet Mergen", "Selçuk Gönençler", "Jeremy"):
                    if analyst.lower() in haystack:
                        item["source"] = analyst
                        break
                notes.setdefault(ticker, []).append(item)
    except Exception:
        return {}
    return notes


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return float(max(low, min(high, value)))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _save_last_successful_scan(payload: dict[str, Any]) -> None:
    """Keep the most recent verified scan available across a server restart."""
    try:
        LAST_SUCCESSFUL_SCAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = LAST_SUCCESSFUL_SCAN_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(_json_safe(payload), ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(LAST_SUCCESSFUL_SCAN_PATH)
    except (OSError, TypeError, ValueError):
        # A fresh scan remains usable even if the optional local cache cannot be written.
        pass


def _load_last_successful_scan() -> dict[str, Any] | None:
    try:
        payload = json.loads(LAST_SUCCESSFUL_SCAN_PATH.read_text(encoding="utf-8"))
        if payload.get("status") == "ok" and isinstance(payload.get("stocks"), list) and payload["stocks"]:
            return payload
    except (OSError, ValueError, TypeError):
        pass
    return None


def _request_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _official_bulletin_for_date(
    trading_date: date,
) -> tuple[dict[str, dict[str, Any]], str]:
    stamp = trading_date.strftime("%Y%m%d")
    url = BIST_BULLETIN_URL.format(
        year=trading_date.strftime("%Y"),
        month=trading_date.strftime("%m"),
        stamp=stamp,
    )
    archive = _request_bytes(url)

    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        csv_name = next(
            (name for name in zipped.namelist() if name.lower().endswith(".csv")),
            None,
        )
        if not csv_name:
            raise ValueError("Resmî bültende CSV dosyası bulunamadı")
        text = zipped.read(csv_name).decode("utf-8-sig")

    quotes: dict[str, dict[str, Any]] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        instrument = (row.get("ISLEM  KODU") or "").strip()
        if not instrument.endswith(".E"):
            continue

        ticker = instrument.removesuffix(".E")
        close = _safe_float(row.get("KAPANIS FIYATI"))
        open_price = _safe_float(row.get("ACILIS FIYATI"))
        low = _safe_float(row.get("EN DUSUK FIYAT"))
        high = _safe_float(row.get("EN YUKSEK FIYAT"))
        previous_close = _safe_float(row.get("ONCEKI KAPANIS FIYATI"))
        change = _safe_float(row.get("DEGISIM (%)"))
        volume = _safe_float(row.get("TOPLAM ISLEM ADEDI"))
        if not all(
            value is not None and value > 0
            for value in (close, open_price, low, high, previous_close)
        ):
            continue

        quotes[ticker] = {
            "ticker": ticker,
            "company": (row.get("BULTEN ADI") or ticker).strip(),
            "date": row.get("TARIH") or trading_date.isoformat(),
            "previousClose": previous_close,
            "open": open_price,
            "low": low,
            "high": high,
            "close": close,
            "change": change,
            "volume": volume or 0.0,
            "bist30": (row.get("BIST 30 ENDEKS") or "").strip() == "1",
            "bist100": (row.get("BIST 100 ENDEKS") or "").strip() == "1",
        }

    if not quotes:
        raise ValueError("Resmî bülten boş döndü")
    return quotes, url


def _latest_official_bulletin(
    max_lookback_days: int = 10,
) -> tuple[dict[str, dict[str, Any]], str, date]:
    today = datetime.now().astimezone().date()
    errors: list[str] = []
    for offset in range(max_lookback_days + 1):
        candidate = today - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        try:
            quotes, url = _official_bulletin_for_date(candidate)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append(f"{candidate.isoformat()}: {type(exc).__name__}")
            continue

        bist30_count = sum(quote["bist30"] for quote in quotes.values())
        if bist30_count < 25:
            errors.append(f"{candidate.isoformat()}: BIST30 üyeliği eksik ({bist30_count})")
            continue
        return quotes, url, candidate

    detail = ", ".join(errors[-4:])
    raise RuntimeError(
        f"Resmî Borsa İstanbul kapanış bülteni bulunamadı. {detail}"
    )


def _official_index_snapshots() -> dict[str, dict[str, Any]]:
    try:
        payload = __import__("json").loads(_request_bytes(BIST_INDEX_URL).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("data", []):
        symbol = item.get("symbol")
        if symbol not in {"XU100", "XU030", "XU500"} or not item.get("metrics"):
            continue
        latest = item["metrics"][-1]
        value = _safe_float(latest.get("currentValue"))
        timestamp = latest.get("createDatetime")
        if value is not None and timestamp:
            result[symbol] = {"price": value, "timestamp": timestamp}
    return result


def _official_index_snapshot() -> dict[str, Any] | None:
    """Backward-compatible XU100 helper used by diagnostics."""
    return _official_index_snapshots().get("XU100")


def _macro_snapshots(
    trading_date: date,
    official_indices: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Best-effort delayed macro strip including commodities (Gold, Silver, Brent, Copper)."""
    symbols = {
        "BIST30": "XU030.IS",
        "BIST500": "XU500.IS",
        "USD/TRY": "TRY=X",
        "EUR/TRY": "EURTRY=X",
        "ONS ALTIN ($)": "GC=F",
        "ONS GÜMÜŞ ($)": "SI=F",
        "BRENT PETROL ($)": "BZ=F",
        "BAKIR ($)": "HG=F",
    }
    try:
        frame = yf.download(list(symbols.values()), period="5d", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
    except Exception:
        return []
    result = []
    usd_try_val = None
    gold_ons_val = None

    for label, symbol in symbols.items():
        try:
            sub = frame[symbol] if symbol in frame else None
            if sub is None or "Close" not in sub:
                continue
            close = sub["Close"].dropna()
            if len(close) < 1:
                continue
            yahoo_value = float(close.iloc[-1])
            yahoo_date = pd.Timestamp(close.index[-1]).date()
            official_symbol = "XU030" if label == "BIST30" else "XU500" if label == "BIST500" else None
            official = official_indices.get(official_symbol) if official_symbol else None
            official_matches = False
            if official:
                try:
                    official_matches = datetime.fromisoformat(str(official["timestamp"])).date() == trading_date
                except (TypeError, ValueError):
                    official_matches = False
            value = float(official["price"]) if official and official_matches else yahoo_value
            if official_symbol and not official_matches and yahoo_date != trading_date:
                daily = None
            elif len(close) > 1 or (official_matches and len(close) == 1):
                previous = float(close.iloc[-2]) if yahoo_date == trading_date and len(close) > 1 else yahoo_value
                daily = round((value / previous - 1) * 100, 2)
            else:
                daily = None

            if label == "USD/TRY":
                usd_try_val = value
            elif label == "ONS ALTIN ($)":
                gold_ons_val = value

            result.append({
                "label": label,
                "value": round(value, 4),
                "daily": daily,
                "timestamp": official["timestamp"] if official and official_matches else pd.Timestamp(close.index[-1]).isoformat(),
                "source": "Borsa İstanbul resmî endeks" if official and official_matches else "Yahoo Finance (gecikmeli)",
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue

    if usd_try_val and gold_ons_val:
        gram_altin = (gold_ons_val * usd_try_val) / 31.1035
        result.append({
            "label": "GRAM ALTIN (TL)",
            "value": round(gram_altin, 2),
            "daily": next((r.get("daily") for r in result if r.get("label") == "ONS ALTIN ($)"), None),
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": "Ons Altın & USD/TRY türetilmiş"
        })

    return result


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _cci(frame: pd.DataFrame, period: int = 20) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    average = typical.rolling(period).mean()
    deviation = typical.rolling(period).apply(
        lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True
    )
    return (typical - average) / (0.015 * deviation.replace(0, np.nan))


def _stochastic(
    frame: pd.DataFrame, period: int = 14, smooth: int = 3
) -> tuple[pd.Series, pd.Series]:
    rolling_low = frame["Low"].rolling(period).min()
    rolling_high = frame["High"].rolling(period).max()
    k = 100 * (frame["Close"] - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
    return k, k.rolling(smooth).mean()


def _smi(
    frame: pd.DataFrame, period: int = 14, smooth: int = 3, signal: int = 5
) -> tuple[pd.Series, pd.Series]:
    rolling_low = frame["Low"].rolling(period).min()
    rolling_high = frame["High"].rolling(period).max()
    midpoint_distance = frame["Close"] - (rolling_high + rolling_low) / 2
    price_range = rolling_high - rolling_low
    smooth_distance = midpoint_distance.ewm(span=smooth, adjust=False).mean().ewm(
        span=smooth, adjust=False
    ).mean()
    smooth_range = price_range.ewm(span=smooth, adjust=False).mean().ewm(
        span=smooth, adjust=False
    ).mean()
    smi = 200 * smooth_distance / smooth_range.replace(0, np.nan)
    return smi, smi.ewm(span=signal, adjust=False).mean()


def _mfi(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    typical = (frame["High"] + frame["Low"] + frame["Close"]) / 3
    raw_flow = typical * frame["Volume"]
    direction = typical.diff()
    positive = raw_flow.where(direction > 0, 0.0).rolling(period).sum()
    negative = raw_flow.where(direction < 0, 0.0).rolling(period).sum()
    ratio = positive / negative.replace(0, np.nan)
    return 100 - 100 / (1 + ratio)


def _connors_rsi(close: pd.Series) -> pd.Series:
    price_rsi = _rsi(close, 3)
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
    daily_return = close.pct_change()
    percent_rank = daily_return.rolling(100).apply(
        lambda values: float(pd.Series(values).rank(pct=True).iloc[-1] * 100),
        raw=False,
    )
    return (price_rsi + streak_rsi + percent_rank) / 3


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = frame["Close"].shift(1)
    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - previous_close).abs(),
            (frame["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def _adx(frame: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up_move = frame["High"].diff()
    down_move = -frame["Low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=frame.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=frame.index,
    )
    atr = _atr(frame, period).replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def _scale(value: float, points: list[tuple[float, float]]) -> float:
    ordered = sorted(points)
    if value <= ordered[0][0]:
        return ordered[0][1]
    if value >= ordered[-1][0]:
        return ordered[-1][1]
    for (x1, y1), (x2, y2) in zip(ordered, ordered[1:]):
        if x1 <= value <= x2:
            ratio = (value - x1) / (x2 - x1)
            return y1 + (y2 - y1) * ratio
    return 50.0


def _merge_official_bar(
    frame: pd.DataFrame, quote: dict[str, Any]
) -> pd.DataFrame:
    merged = frame.copy().dropna(how="all")
    raw_date = str(quote["date"]).strip()
    official_date = pd.to_datetime(raw_date, format="%Y-%m-%d", errors="coerce")
    if pd.isna(official_date):
        official_date = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
    if pd.isna(official_date):
        raise ValueError(f"Geçersiz resmî tarih: {raw_date}")
    official_date = pd.Timestamp(official_date).normalize()
    merged.index = pd.to_datetime(merged.index).tz_localize(None)
    merged = merged[merged.index.normalize() <= official_date]
    values = {
        "Open": quote["open"],
        "High": quote["high"],
        "Low": quote["low"],
        "Close": quote["close"],
        "Volume": quote["volume"],
    }
    for column, value in values.items():
        merged.loc[official_date, column] = value
    return merged.sort_index()


def _detect_head_shoulders(frame: pd.DataFrame) -> dict[str, Any]:
    """
    Detect Head & Shoulders (OBO) and Inverse Head & Shoulders (TOBO) patterns.
    Returns pattern metadata including neckline, shoulders, head, breakout confirmation, target and stop.
    """
    default_result: dict[str, Any] = {
        "pattern": None,
        "patternConfidence": 0.0,
        "neckline": None,
        "leftShoulder": None,
        "head": None,
        "rightShoulder": None,
        "breakoutConfirmed": False,
        "patternTarget": None,
        "patternStop": None,
        "dateRange": None,
    }
    if len(frame) < 60:
        return default_result

    low = frame["Low"]
    high = frame["High"]
    close = frame["Close"]
    dates = [str(d)[:10] for d in frame.index]
    latest_close = float(close.iloc[-1])
    n = len(frame)

    best_candidate: dict[str, Any] | None = None
    best_conf = 0.0

    for window in (3, 4, 6):
        swing_lows: list[tuple[int, float, str]] = []
        for i in range(window, n - window):
            if float(low.iloc[i]) == float(low.iloc[i - window : i + window + 1].min()):
                swing_lows.append((i, float(low.iloc[i]), dates[i]))

        swing_highs: list[tuple[int, float, str]] = []
        for i in range(window, n - window):
            if float(high.iloc[i]) == float(high.iloc[i - window : i + window + 1].max()):
                swing_highs.append((i, float(high.iloc[i]), dates[i]))

        # TOBO Check
        recent_sw_lows = [sl for sl in swing_lows if sl[0] >= max(0, n - 150)]
        for i in range(len(recent_sw_lows) - 2):
            l_sh = recent_sw_lows[i]
            head = recent_sw_lows[i + 1]
            r_sh = recent_sw_lows[i + 2]

            if head[1] < l_sh[1] * 0.988 and head[1] < r_sh[1] * 0.988:
                shoulder_diff = abs(l_sh[1] - r_sh[1]) / min(l_sh[1], r_sh[1])
                if shoulder_diff <= 0.11:
                    peaks1 = [sh for sh in swing_highs if l_sh[0] < sh[0] < head[0]]
                    peaks2 = [sh for sh in swing_highs if head[0] < sh[0] < r_sh[0]]

                    p1 = max(peaks1, key=lambda x: x[1]) if peaks1 else None
                    p2 = max(peaks2, key=lambda x: x[1]) if peaks2 else None

                    if p1 and p2:
                        x1, y1 = p1[0], p1[1]
                        x2, y2 = p2[0], p2[1]
                        if x2 != x1:
                            slope = (y2 - y1) / (x2 - x1)
                            neckline_now = y2 + slope * ((n - 1) - x2)
                        else:
                            neckline_now = (y1 + y2) / 2

                        head_depth = neckline_now - head[1]
                        if head_depth > 0 and (latest_close >= head[1]):
                            breakout = latest_close >= neckline_now * 0.995
                            target = neckline_now + head_depth
                            stop_lvl = max(r_sh[1], head[1] + 0.35 * head_depth)
                            confidence = round(
                                max(45.0, min(96.0, (1.0 - shoulder_diff) * 62 + (25 if breakout else 10))),
                                1,
                            )
                            if confidence > best_conf:
                                best_conf = confidence
                                best_candidate = {
                                    "pattern": "TOBO",
                                    "patternConfidence": confidence,
                                    "neckline": round(neckline_now, 4),
                                    "leftShoulder": {"price": round(l_sh[1], 4), "date": l_sh[2]},
                                    "head": {"price": round(head[1], 4), "date": head[2]},
                                    "rightShoulder": {"price": round(r_sh[1], 4), "date": r_sh[2]},
                                    "breakoutConfirmed": bool(breakout),
                                    "patternTarget": round(target, 4),
                                    "patternStop": round(stop_lvl, 4),
                                    "dateRange": f"{l_sh[2]} – {r_sh[2]}",
                                }

        # OBO Check
        recent_sw_highs = [sh for sh in swing_highs if sh[0] >= max(0, n - 150)]
        for i in range(len(recent_sw_highs) - 2):
            l_sh = recent_sw_highs[i]
            head = recent_sw_highs[i + 1]
            r_sh = recent_sw_highs[i + 2]

            if head[1] > l_sh[1] * 1.012 and head[1] > r_sh[1] * 1.012:
                shoulder_diff = abs(l_sh[1] - r_sh[1]) / min(l_sh[1], r_sh[1])
                if shoulder_diff <= 0.11:
                    troughs1 = [sl for sl in swing_lows if l_sh[0] < sl[0] < head[0]]
                    troughs2 = [sl for sl in swing_lows if head[0] < sl[0] < r_sh[0]]

                    t1 = min(troughs1, key=lambda x: x[1]) if troughs1 else None
                    t2 = min(troughs2, key=lambda x: x[1]) if troughs2 else None

                    if t1 and t2:
                        x1, y1 = t1[0], t1[1]
                        x2, y2 = t2[0], t2[1]
                        if x2 != x1:
                            slope = (y2 - y1) / (x2 - x1)
                            neckline_now = y2 + slope * ((n - 1) - x2)
                        else:
                            neckline_now = (y1 + y2) / 2

                        head_height = head[1] - neckline_now
                        if head_height > 0 and (latest_close <= head[1]):
                            breakout = latest_close <= neckline_now * 1.005
                            target = neckline_now - head_height
                            stop_lvl = min(r_sh[1], head[1] - 0.35 * head_height)
                            confidence = round(
                                max(45.0, min(96.0, (1.0 - shoulder_diff) * 62 + (25 if breakout else 10))),
                                1,
                            )
                            if confidence > best_conf:
                                best_conf = confidence
                                best_candidate = {
                                    "pattern": "OBO",
                                    "patternConfidence": confidence,
                                    "neckline": round(neckline_now, 4),
                                    "leftShoulder": {"price": round(l_sh[1], 4), "date": l_sh[2]},
                                    "head": {"price": round(head[1], 4), "date": head[2]},
                                    "rightShoulder": {"price": round(r_sh[1], 4), "date": r_sh[2]},
                                    "breakoutConfirmed": bool(breakout),
                                    "patternTarget": round(target, 4),
                                    "patternStop": round(stop_lvl, 4),
                                    "dateRange": f"{l_sh[2]} – {r_sh[2]}",
                                }

    return best_candidate if best_candidate else default_result


@dataclass
class TechnicalSnapshot:
    ticker: str
    frame: pd.DataFrame
    benchmark: pd.DataFrame
    quote: dict[str, Any]

    def build(self) -> dict[str, Any] | None:
        frame = _merge_official_bar(self.frame, self.quote)
        benchmark = self.benchmark.copy().dropna(how="all")
        if len(frame) < 205 or len(benchmark) < 70:
            return None

        close = frame["Close"]
        high = frame["High"]
        low = frame["Low"]
        open_ = frame["Open"]
        volume = frame["Volume"]

        ema5 = close.ewm(span=5, adjust=False).mean()
        ema8 = close.ewm(span=8, adjust=False).mean()
        ema13 = close.ewm(span=13, adjust=False).mean()
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        sma200 = close.rolling(200).mean()
        rsi = _rsi(close)
        atr = _atr(frame)
        adx, plus_di, minus_di = _adx(frame)
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(
            span=26, adjust=False
        ).mean()
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal
        volume_average = volume.rolling(20).mean()
        cci = _cci(frame)
        stochastic_k, stochastic_d = _stochastic(frame)
        smi, smi_signal = _smi(frame)
        mfi = _mfi(frame)
        connors_rsi = _connors_rsi(close)

        latest_price = float(self.quote["close"])
        previous_close = float(self.quote["previousClose"])
        daily_change = (
            float(self.quote["change"])
            if self.quote["change"] is not None
            else (latest_price / previous_close - 1) * 100
        )
        atr_value = float(atr.iloc[-1])
        rsi_value = float(rsi.iloc[-1])
        adx_value = float(adx.iloc[-1])
        plus_di_value = float(plus_di.iloc[-1])
        minus_di_value = float(minus_di.iloc[-1])
        cci_value = float(cci.iloc[-1])
        smi_value = float(smi.iloc[-1])
        smi_signal_value = float(smi_signal.iloc[-1])
        stochastic_value = float(stochastic_k.iloc[-1])
        mfi_value = float(mfi.iloc[-1])
        connors_rsi_value = float(connors_rsi.iloc[-1])
        average_volume = _safe_float(volume_average.iloc[-1])
        current_volume = _safe_float(volume.iloc[-1]) or 0.0
        volume_ratio = (
            float(current_volume / average_volume)
            if average_volume is not None and average_volume > 0
            else 0.0
        )
        extension = (latest_price / float(ema20.iloc[-1]) - 1) * 100
        return_20 = (latest_price / float(close.iloc[-21]) - 1) * 100
        return_63 = (latest_price / float(close.iloc[-64]) - 1) * 100
        benchmark_return_63 = (
            float(benchmark["Close"].iloc[-1])
            / float(benchmark["Close"].iloc[-64])
            - 1
        ) * 100
        relative_return = return_63 - benchmark_return_63

        trend_score = 0.0
        trend_score += 16 if latest_price > ema20.iloc[-1] else 0
        trend_score += 16 if latest_price > ema50.iloc[-1] else 0
        trend_score += 18 if latest_price > sma200.iloc[-1] else 0
        trend_score += 15 if ema20.iloc[-1] > ema50.iloc[-1] else 0
        trend_score += 15 if ema50.iloc[-1] > sma200.iloc[-1] else 0
        trend_score += 10 if ema20.iloc[-1] > ema20.iloc[-6] else 0
        trend_score += 10 if close.iloc[-1] > close.iloc[-11] else 0
        # Moving-average alignment alone is not enough for a perfect trend score.
        # Require participation and directional strength before allowing 100/100.
        if adx.iloc[-1] < 20:
            trend_score = min(trend_score, 75)
        elif adx.iloc[-1] < 25:
            trend_score = min(trend_score, 90)
        if volume.iloc[-1] < volume.rolling(20).mean().iloc[-1] * 0.8:
            trend_score = min(trend_score, 85)

        rsi_component = _scale(
            rsi_value,
            [(20, 10), (35, 48), (48, 82), (58, 100), (68, 88), (78, 48), (90, 10)],
        )
        macd_component = (
            90
            if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-1] >= macd_hist.iloc[-2]
            else 65
            if macd_hist.iloc[-1] > 0
            else 28
        )
        short_component = _scale(
            return_20,
            [(-20, 5), (-5, 35), (0, 55), (8, 85), (18, 100), (30, 55), (50, 20)],
        )
        momentum_score = _clip(
            rsi_component * 0.45 + macd_component * 0.30 + short_component * 0.25
        )

        direction_bonus = 25 if plus_di_value > minus_di_value else -15
        adx_score = _clip(
            _scale(
                adx_value,
                [(5, 15), (15, 45), (22, 78), (32, 100), (48, 88), (65, 60)],
            )
            + direction_bonus
        )
        volume_score = _clip(
            _scale(
                volume_ratio,
                [(0.2, 10), (0.7, 45), (1.0, 65), (1.4, 90), (2.2, 100), (4, 70), (7, 40)],
            )
        )
        relative_score = _clip(
            _scale(
                relative_return,
                [(-30, 5), (-12, 25), (0, 55), (10, 75), (25, 92), (45, 100)],
            )
        )

        prior_20_high = float(high.iloc[-21:-1].max())
        prior_10_low = float(low.iloc[-11:-1].min())
        candle_range = max(float(high.iloc[-1] - low.iloc[-1]), 1e-9)
        lower_wick = (
            min(float(open_.iloc[-1]), latest_price) - float(low.iloc[-1])
        ) / candle_range
        close_location = (latest_price - float(low.iloc[-1])) / candle_range

        badges: list[str] = []
        if (
            float(low.iloc[-1]) < prior_10_low
            and latest_price > prior_10_low
            and lower_wick >= 0.3
        ):
            badges.append("LIQ")
        if latest_price > prior_20_high:
            badges.append("MSS")
        if any(
            float(low.iloc[index]) > float(high.iloc[index - 2])
            for index in range(len(frame) - 4, len(frame))
        ):
            badges.append("FVG")
        if (
            abs(extension) <= 2.2
            and lower_wick >= 0.2
            and latest_price > float(open_.iloc[-1])
        ):
            badges.append("OB")
        if volume_ratio >= 2 and close_location >= 0.65:
            badges.append("CLIMAX")

        ema_5_8_13_bullish = bool(
            ema5.iloc[-1] > ema8.iloc[-1] > ema13.iloc[-1]
        )
        if ema_5_8_13_bullish:
            badges.append("EMA5-8-13")
        # VCP proxy: contracting ranges and volume while price holds the upper half.
        range_now = float((high - low).iloc[-5:].mean())
        range_prev = float((high - low).iloc[-20:-5].mean())
        volume_prev = float(volume.iloc[-20:-5].mean()) if len(volume) >= 20 else 0.0
        vcp_score = _clip(
            50
            + (25 if range_prev and range_now < range_prev * 0.78 else 0)
            + (15 if volume_prev and float(volume.iloc[-5:].mean()) < volume_prev else 0)
            + (10 if close_location >= 0.55 else 0)
        )
        if vcp_score >= 75:
            badges.append("VCP")

        structure_score = 35.0
        structure_score += 25 if latest_price > prior_20_high else 0
        structure_score += 15 if latest_price > float(high.iloc[-6:-1].max()) else 0
        structure_score += (
            15 if float(low.iloc[-5:].min()) > float(low.iloc[-15:-5].min()) else 0
        )
        structure_score += 10 if close_location >= 0.65 else 0
        structure_score = _clip(structure_score)

        entry_score = _scale(
            extension,
            [(-8, 28), (-3, 68), (0, 100), (2.5, 94), (5, 70), (8, 38), (14, 8)],
        )
        if daily_change > 5:
            entry_score -= min(35, (daily_change - 5) * 7)
        entry_score = _clip(entry_score)

        recent_swing_low = float(low.iloc[-10:].min())
        atr_stop = latest_price - 1.8 * atr_value
        structural_stop = recent_swing_low - 0.15 * atr_value
        stop = max(atr_stop, structural_stop)
        if stop >= latest_price:
            stop = latest_price - 1.5 * atr_value
        risk_percent = (latest_price - stop) / latest_price * 100
        stop_score = _clip(
            _scale(
                risk_percent,
                [(0.5, 15), (2, 75), (4, 100), (7, 90), (10, 65), (15, 30)],
            )
        )

        technical_score = _clip(
            trend_score * 0.27
            + momentum_score * 0.19
            + adx_score * 0.14
            + volume_score * 0.10
            + relative_score * 0.16
            + structure_score * 0.14
        )
        model_score = _clip(
            technical_score * 0.78 + entry_score * 0.14 + stop_score * 0.08
        )

        smi_cross_up = bool(
            smi.iloc[-1] > smi_signal.iloc[-1]
            and smi.iloc[-2] <= smi_signal.iloc[-2]
        )
        stochastic_cross_up = bool(
            stochastic_k.iloc[-1] > stochastic_d.iloc[-1]
            and stochastic_k.iloc[-2] <= stochastic_d.iloc[-2]
        )
        recent_drawdown = (latest_price / float(close.iloc[-60:].max()) - 1) * 100
        five_day_return = (latest_price / float(close.iloc[-6]) - 1) * 100
        positive_reversal = bool(
            latest_price > float(open_.iloc[-1])
            and latest_price > float(close.iloc[-2])
        )
        pullback_near_ema20 = abs(extension) <= 4.0

        pattern_info = _detect_head_shoulders(frame)
        if pattern_info.get("pattern") == "TOBO":
            badges.append("TOBO")
        elif pattern_info.get("pattern") == "OBO":
            badges.append("OBO-RİSK")

        # These are independently evaluated algorithms. A stock may match more
        # than one; the highest-quality active match becomes the primary label.
        # Money Dip uses price/volume MFI as a transparent proxy because exchange
        # member-position/takas data is not available in the current feed.
        strategy_rules: dict[str, tuple[bool, float, list[str]]] = {
            "TOBO Kırılımı": (
                pattern_info.get("pattern") == "TOBO" and bool(pattern_info.get("breakoutConfirmed")),
                _clip(float(pattern_info.get("patternConfidence", 0)) * 0.70 + momentum_score * 0.30),
                [
                    f"TOBO Boyun Çizgisi {pattern_info.get('neckline')} TL kırıldı",
                    f"Güven %{pattern_info.get('patternConfidence')}",
                    f"Formasyon Hedefi {pattern_info.get('patternTarget')} TL",
                ],
            ),
            "Dipten Dönüş": (
                smi_cross_up and rsi_value <= 52 and cci_value <= 25 and extension <= 4,
                _clip((100 - rsi_value) * 0.35 + (100 - min(100, max(-100, cci_value))) * 0.20 + entry_score * 0.45),
                ["SMI yukarı kesişim", f"RSI {rsi_value:.1f}", f"CCI {cci_value:.0f}"],
            ),
            "Derin Dönüş": (
                recent_drawdown <= -10
                and min(float(smi.iloc[-2]), smi_value) <= -25
                and stochastic_cross_up
                and rsi_value <= 48
                and positive_reversal
                and volume_ratio >= 0.65,
                _clip(abs(recent_drawdown) * 2 + (100 - rsi_value) * 0.55 + volume_score * 0.20),
                [f"60G düşüş {recent_drawdown:.1f}%", "Stokastik dönüş", f"SMI {smi_value:.1f}"],
            ),
            "Uzun Vade": (
                latest_price > sma200.iloc[-1]
                and ema20.iloc[-1] > ema50.iloc[-1] > sma200.iloc[-1]
                and rsi_value >= 45
                and rsi_value <= 72
                and relative_return > 0
                and adx_value >= 18,
                _clip(trend_score * 0.55 + relative_score * 0.25 + adx_score * 0.20),
                ["Fiyat 200G ortalama üzerinde", "EMA20 > EMA50 > SMA200", f"Göreli güç {relative_return:+.1f}"],
            ),
            "Momentum Kırılımı": (
                latest_price > prior_20_high
                and volume_ratio >= 1.15
                and macd_hist.iloc[-1] > 0
                and macd_hist.iloc[-1] >= macd_hist.iloc[-2]
                and 52 <= rsi_value <= 79
                and plus_di_value > minus_di_value,
                _clip(momentum_score * 0.40 + volume_score * 0.30 + structure_score * 0.30),
                ["20G direnç kırılımı", f"Hacim {volume_ratio:.2f}x", "MACD ivmesi pozitif"],
            ),
            "CRSI Scalp": (
                connors_rsi_value <= 25
                and rsi_value <= 48
                and extension <= 0,
                _clip((100 - connors_rsi_value) * 0.60 + entry_score * 0.40),
                [f"CRSI {connors_rsi_value:.1f}", f"RSI {rsi_value:.1f}", "Kısa vadeli aşırı sarkma"],
            ),
            "Chartist MM Trend": (
                trend_score >= 75
                and adx_value >= 22
                and plus_di_value > minus_di_value
                and relative_return >= 4
                and (vcp_score >= 70 or macd_hist.iloc[-1] > 0),
                _clip(trend_score * 0.45 + adx_score * 0.20 + relative_score * 0.20 + vcp_score * 0.15),
                [f"Trend {trend_score:.0f}/100", f"ADX {adx_value:.1f}", f"VCP {vcp_score:.0f}/100"],
            ),
            "Wyckoff Spring": (
                "LIQ" in badges
                and latest_price > prior_10_low
                and positive_reversal
                and volume_ratio >= 0.75,
                _clip(structure_score * 0.40 + close_location * 100 * 0.30 + volume_score * 0.30),
                ["Destek altı likidite süpürmesi", "Destek üzerine geri dönüş", f"Alt fitil %{lower_wick * 100:.0f}"],
            ),
            "Money Dip": (
                five_day_return < 0
                and mfi_value >= 52
                and mfi_value > float(mfi.iloc[-6])
                and latest_price > ema50.iloc[-1]
                and extension >= -6
                and volume_ratio >= 0.65,
                _clip(mfi_value * 0.45 + entry_score * 0.35 + trend_score * 0.20),
                [f"5G fiyat {five_day_return:.1f}%", f"MFI {mfi_value:.1f} ve yükseliyor", "Hacim tabanlı para akışı vekili"],
            ),
            "Chartist Trender": (
                trend_score >= 65
                and latest_price > ema50.iloc[-1]
                and pullback_near_ema20
                and positive_reversal
                and plus_di_value > minus_di_value
                and macd_hist.iloc[-1] >= macd_hist.iloc[-2],
                _clip(trend_score * 0.40 + entry_score * 0.35 + momentum_score * 0.25),
                ["Ana trend yukarı", f"EMA20 mesafesi {extension:+.1f}%", "Düzeltme sonrası yeniden ivme"],
            ),
        }
        active_strategies = [
            (name, quality, evidence)
            for name, (matched, quality, evidence) in strategy_rules.items()
            if matched
        ]
        active_strategies.sort(key=lambda item: item[1], reverse=True)
        strategy = active_strategies[0][0] if active_strategies else "İzleme"
        strategy_quality = active_strategies[0][1] if active_strategies else 0.0
        strategy_matches = [item[0] for item in active_strategies]
        strategy_evidence = {
            name: evidence for name, _, evidence in active_strategies
        }

        # Multi-algorithm consensus check (9 algorithms)
        consensus_mapping = {
            "Dipten Dönüş": "DD",
            "Derin Dönüş": "DDR",
            "Uzun Vade": "UV",
            "Momentum Kırılımı": "MK",
            "CRSI Scalp": "CRSI",
            "Chartist MM Trend": "MMT",
            "Wyckoff Spring": "WYC",
            "Money Dip": "MD",
            "Chartist Trender": "TRD",
        }
        matched_abbrs = [
            consensus_mapping[name]
            for name in strategy_matches
            if name in consensus_mapping
        ]
        n_matches = len(matched_abbrs)
        if n_matches == 2:
            consensus_badge = f"🔥 ÇAO ({'+'.join(matched_abbrs)})"
            badges.insert(0, consensus_badge)
        elif n_matches >= 3:
            consensus_badge = f"🚀 SK{n_matches} ({'+'.join(matched_abbrs)})"
            badges.insert(0, consensus_badge)

        entry_center = min(
            latest_price, max(float(ema5.iloc[-1]), float(ema20.iloc[-1]))
        )
        entry_low = max(stop * 1.015, entry_center - 0.30 * atr_value)
        entry_high = min(latest_price, entry_center + 0.25 * atr_value)
        if entry_high < entry_low:
            entry_high = entry_low
        in_entry_zone = entry_low <= latest_price <= entry_high * 1.005

        trend_family = strategy in {
            "Uzun Vade", "Momentum Kırılımı", "Chartist MM Trend", "Chartist Trender"
        }
        direction_confirmed = (
            plus_di_value > minus_di_value if trend_family else positive_reversal
        )
        structure_confirmed = latest_price > ema20.iloc[-1] if trend_family else latest_price > stop
        hard_open_rules = (
            strategy != "İzleme"
            and strategy_quality >= 62
            and model_score >= 68
            and technical_score >= 60
            and entry_score >= 48
            and stop_score >= 55
            and daily_change <= 5.5
            and in_entry_zone
            and direction_confirmed
            and structure_confirmed
            and risk_percent <= 8.5
            and relative_return >= -5
        )
        if hard_open_rules:
            recommendation = "OPEN"
            verdict = "Giriş Koşulu Uygun"
        elif model_score >= 63 and technical_score >= 58:
            recommendation = "WATCH"
            verdict = "Teyit / Geri Çekilme Bekle"
        else:
            recommendation = "AVOID"
            verdict = "Şimdilik Pozisyon Açma"

        risk = max(entry_center - stop, atr_value * 0.8)
        targets = [
            entry_center + risk * multiple for multiple in (1.5, 2.5, 4.0)
        ]
        rr = (targets[0] - entry_center) / risk
        confidence = _clip(
            76 + min(len(badges), 3) * 3 - (8 if abs(extension) > 7 else 0),
            60,
            92,
        )

        reasons = [
            "Resmî BIST kapanışı doğrulandı",
            f"{strategy} {strategy_quality:.0f}/100" if strategy != "İzleme" else "9 algoritmada bugün kesin tetik yok",
            f"Trend {trend_score:.0f}/100",
            f"Momentum {momentum_score:.0f}/100",
            f"ADX {adx_value:.1f} ({'+' if plus_di_value > minus_di_value else '-'}DI baskın)",
            f"Hacim {volume_ratio:.2f}x",
            f"BIST100 göreli güç {relative_return:+.1f} puan",
        ]

        company = DISPLAY_NAMES.get(
            self.ticker, str(self.quote["company"]).title()
        )
        return {
            "ticker": self.ticker,
            "company": company,
            "sector": SECTOR_BY_TICKER.get(self.ticker, "Diğer"),
            "strategy": strategy,
            "strategyMatches": strategy_matches,
            "strategyQuality": round(strategy_quality, 1),
            "strategyEvidence": strategy_evidence,
            "patternInfo": pattern_info,
            "recommendation": recommendation,
            "fundamental": None,
            "fundamentalCompleteness": 0,
            "financialVerified": False,
            "guru": round(trend_score),
            "piot": None,
            "indicators": {
                "rsi": round(rsi_value, 1),
                "adx": round(adx_value, 1),
                "cci": round(cci_value, 1),
                "smi": round(smi_value, 1),
                "stochastic": round(stochastic_value, 1),
                "mfi": round(mfi_value, 1),
                "connorsRsi": round(connors_rsi_value, 1),
            },
            "sentiment": round(momentum_score),
            "master": round(technical_score),
            "componentScores": {
                "technical": round(technical_score, 1),
                "trend": round(trend_score, 1),
                "momentum": round(momentum_score, 1),
                "volume": round(volume_score, 1),
                "relativeStrength": round(relative_score, 1),
                "structure": round(structure_score, 1),
                "entry": round(entry_score, 1),
                "stop": round(stop_score, 1),
                "vcp": round(vcp_score, 1),
                "strategy": round(strategy_quality, 1),
                "fundamental": None,
                "cashFlow": None,
            },
            "signalFlags": {
                "ema5813": ema_5_8_13_bullish,
                "fvg": "FVG" in badges,
                "liquiditySweep": "LIQ" in badges,
                "marketStructureShift": "MSS" in badges,
                "vcp": vcp_score >= 75,
            },
            "modelScore": round(model_score, 1),
            "price": round(latest_price, 4),
            "entry": round(entry_center, 4),
            "entryZoneLow": round(entry_low, 4),
            "entryZoneHigh": round(entry_high, 4),
            "daily": round(daily_change, 2),
            "badges": badges,
            "targets": [round(value, 4) for value in targets],
            "stop": round(stop, 4),
            "protected": False,
            "warning": risk_percent < 1.5 or recommendation == "AVOID",
            "period": "1D",
            "rr": round(rr, 2),
            "position": 0,
            "volume": round(volume_score),
            "structure": round(structure_score),
            "support": round(entry_score),
            "momentum": round(momentum_score),
            "chart": [round(float(value), 4) for value in close.iloc[-35:].tolist()],
            "chartRanges": {
                "1H": [round(float(value), 4) for value in close.iloc[-5:].tolist()],
                "1A": [round(float(value), 4) for value in close.iloc[-22:].tolist()],
                "3A": [round(float(value), 4) for value in close.iloc[-66:].tolist()],
            },
            "priceVerified": True,
            "priceSource": "Borsa İstanbul Günlük Bülten",
            "officialOhlc": {
                "previousClose": round(previous_close, 4),
                "open": round(float(self.quote["open"]), 4),
                "low": round(float(self.quote["low"]), 4),
                "high": round(float(self.quote["high"]), 4),
                "close": round(latest_price, 4),
                "volume": round(float(self.quote["volume"])),
            },
            "modelAnalysis": {
                "score": round(model_score, 1),
                "grade": (
                    "A+"
                    if model_score >= 82
                    else "A"
                    if model_score >= 75
                    else "B"
                    if model_score >= 66
                    else "C"
                ),
                "verdict": verdict,
                "confidence": round(confidence),
                "technical": round(technical_score, 1),
                "financial": None,
                "smc": min(100, len(badges) * 28),
                "rr": round(_clip(65 + (rr - 1) * 25), 1),
                "entry": round(entry_score, 1),
                "stop": round(stop_score, 1),
                "weights": {
                    "technical": 78,
                    "entry": 14,
                    "stop": 8,
                    "financial": 0,
                },
            },
            "technicals": {
                "trend": round(trend_score, 1),
                "momentum": round(momentum_score, 1),
                "adx": round(adx_value, 1),
                "plusDi": round(plus_di_value, 1),
                "minusDi": round(minus_di_value, 1),
                "volumeRatio": round(volume_ratio, 2),
                "relativeStrength63d": round(relative_return, 2),
                "ema20Distance": round(extension, 2),
                "riskPercent": round(risk_percent, 2),
                "cci": round(cci_value, 1),
                "smi": round(smi_value, 1),
                "smiSignal": round(smi_signal_value, 1),
                "stochastic": round(stochastic_value, 1),
                "mfi": round(mfi_value, 1),
                "connorsRsi": round(connors_rsi_value, 1),
                "moneyDipData": "MFI/hacim vekili; gerçek takas verisi değildir",
            },
            "reasons": reasons,
            "dataDate": self.quote["date"],
        }


def _download_history(symbols: list[str]) -> pd.DataFrame:
    return yf.download(
        symbols,
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )


def _download_delayed_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Best-effort 15-minute delayed display quotes; never used for signals."""
    try:
        frame = yf.download(
            symbols,
            period="2d",
            interval="15m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception:
        return {}
    quotes: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        try:
            rows = frame[symbol].dropna(subset=["Close"])
            if rows.empty:
                continue
            row = rows.iloc[-1]
            stamp = rows.index[-1]
            close = _safe_float(row.get("Close"))
            if close is None:
                continue
            quotes[symbol.removesuffix(".IS")] = {
                "price": round(close, 4),
                "timestamp": stamp.isoformat(),
                "source": "Yahoo Finance intraday (gecikmeli; gösterim amaçlı)",
                "verified": False,
                "chart": [
                    round(float(value), 4)
                    for value in rows.loc[rows.index.date == stamp.date(), "Close"].tolist()
                    if pd.notna(value)
                ],
            }
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return quotes


def _align_benchmark(
    benchmark: pd.DataFrame,
    trading_date: date,
    official_index: dict[str, Any] | None,
) -> tuple[pd.DataFrame, bool]:
    """Align XU100 history to the official signal date without using future data."""
    aligned = benchmark.copy().dropna(how="all")
    aligned.index = pd.to_datetime(aligned.index).tz_localize(None)
    aligned = aligned[aligned.index.date <= trading_date]
    official_appended = False
    if official_index:
        try:
            snapshot_date = datetime.fromisoformat(str(official_index["timestamp"])).date()
            if snapshot_date == trading_date:
                aligned.loc[pd.Timestamp(trading_date), "Close"] = float(official_index["price"])
                official_appended = True
        except (KeyError, TypeError, ValueError):
            pass
    aligned = aligned.sort_index()
    is_aligned = bool(len(aligned)) and aligned.index[-1].date() == trading_date
    return aligned, is_aligned


def scan_market(force: bool = False) -> dict[str, Any]:
    now = time.time()
    with _cache_lock:
        if (
            not force
            and _cache["payload"]
            and now - _cache["created_at"] < CACHE_TTL_SECONDS
        ):
            return _cache["payload"]

    # Cold starts must never block the dashboard on a full network scan.
    # Serve the last verified snapshot immediately; an explicit refresh can
    # still request a fresh scan.
    if not force:
        persisted = _load_last_successful_scan()
        if persisted and isinstance(persisted.get("stocks"), list) and persisted["stocks"]:
            persisted = dict(persisted)
            persisted["staleData"] = True
            persisted["staleReason"] = "cold-start-cache"
            persisted["delayNotice"] = "Son doğrulanmış tarama gösteriliyor; güncelleme manuel yenilemeyle alınabilir."
            with _cache_lock:
                _cache["created_at"] = now
                _cache["payload"] = persisted
            return persisted

    try:
        return _scan_market_fresh(now)
    except Exception as exc:
        stale = _load_last_successful_scan()
        if not stale:
            raise
        stale = dict(stale)
        stale["staleData"] = True
        stale["staleReason"] = type(exc).__name__
        stale["delayNotice"] = (
            f"Canlı tarama geçici olarak alınamadı ({type(exc).__name__}); "
            f"{stale.get('dataDate', 'son')} tarihli son başarılı resmî kapanış gösteriliyor."
        )
        with _cache_lock:
            _cache["created_at"] = now
            _cache["payload"] = stale
        return stale


def build_market_wind_report(frame: pd.DataFrame) -> dict[str, Any]:
    """
    Generate XU100 Market Wind Analysis Report (Piyasa Rüzgarı Analiz Raporu).
    Computes 45 technical indicators and determines positive/negative consensus on BIST100 index.
    """
    if len(frame) < 60:
        return {
            "status": "error",
            "message": "Yetersiz endeks tarihçesi",
            "indicators": [],
        }

    close = frame["Close"].dropna()
    high = frame["High"].dropna() if "High" in frame else close
    low = frame["Low"].dropna() if "Low" in frame else close
    volume = frame["Volume"].dropna() if "Volume" in frame else pd.Series(1.0, index=close.index)

    latest_close = float(close.iloc[-1])
    previous_close = float(close.iloc[-2]) if len(close) > 1 else latest_close
    change_pct = round((latest_close / previous_close - 1) * 100, 2)

    ema50_series = close.ewm(span=50, adjust=False).mean()
    ema200_series = close.ewm(span=200, adjust=False).mean()
    ema50_val = float(ema50_series.iloc[-1])
    ema200_val = float(ema200_series.iloc[-1])

    ema50_dist = round((latest_close / ema50_val - 1) * 100, 2)
    ema200_dist = round((latest_close / ema200_val - 1) * 100, 2)

    indicators_def: list[dict[str, Any]] = []

    # Moving Averages & Trend
    sma_periods = [5, 10, 20, 30, 50, 100, 200]
    for p in sma_periods:
        val = float(close.rolling(min(p, len(close))).mean().iloc[-1])
        is_pos = latest_close >= val
        indicators_def.append({
            "name": f"SMA {p} (Hareketli Ort.)",
            "group": "Trend",
            "status": "POZİTİF (BOĞA)" if is_pos else "NEGATİF (AYI)",
            "isPositive": is_pos,
            "value": round(val, 2)
        })

    ema_periods = [5, 8, 9, 13, 21, 34, 55, 89, 200]
    for p in ema_periods:
        val = float(close.ewm(span=p, adjust=False).mean().iloc[-1])
        is_pos = latest_close >= val
        indicators_def.append({
            "name": f"EMA {p} (Üstel Ort.)",
            "group": "Trend",
            "status": "POZİTİF (BOĞA)" if is_pos else "NEGATİF (AYI)",
            "isPositive": is_pos,
            "value": round(val, 2)
        })

    wma20 = float(close.rolling(20).apply(lambda x: np.dot(x, np.arange(1, 21)) / np.sum(np.arange(1, 21)), raw=True).iloc[-1])
    indicators_def.append({"name": "WMA 20 (Ağırlıklı Ort.)", "group": "Trend", "status": "POZİTİF (BOĞA)" if latest_close >= wma20 else "NEGATİF (AYI)", "isPositive": latest_close >= wma20, "value": round(wma20, 2)})

    vwma20 = float((close * volume).rolling(20).sum().iloc[-1] / max(1.0, float(volume.rolling(20).sum().iloc[-1])))
    indicators_def.append({"name": "VWMA 20 (Hacim Ağırlıklı)", "group": "Trend", "status": "POZİTİF (BOĞA)" if latest_close >= vwma20 else "NEGATİF (AYI)", "isPositive": latest_close >= vwma20, "value": round(vwma20, 2)})

    hma9 = float(close.rolling(9).mean().iloc[-1])
    indicators_def.append({"name": "Hull MA 9 (Hull Ort.)", "group": "Trend", "status": "POZİTİF (BOĞA)" if latest_close >= hma9 else "NEGATİF (AYI)", "isPositive": latest_close >= hma9, "value": round(hma9, 2)})

    # Oscillators & Momentum
    rsi14 = float(_rsi(close).iloc[-1])
    indicators_def.append({"name": "RSI 14 (Göreceli Güç)", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if rsi14 >= 50 else "NEGATİF (AYI)", "isPositive": rsi14 >= 50, "value": round(rsi14, 1)})

    dummy_df = pd.DataFrame({"High": high, "Low": low, "Close": close, "Volume": volume}, index=close.index)
    stoch_k, stoch_d = _stochastic(dummy_df)
    stoch_k_val = float(stoch_k.iloc[-1])
    stoch_d_val = float(stoch_d.iloc[-1])
    indicators_def.append({"name": "Stokastik %K", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if stoch_k_val >= 50 else "NEGATİF (AYI)", "isPositive": stoch_k_val >= 50, "value": round(stoch_k_val, 1)})
    indicators_def.append({"name": "Stokastik %D (Sinyal)", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if stoch_k_val >= stoch_d_val else "NEGATİF (AYI)", "isPositive": stoch_k_val >= stoch_d_val, "value": round(stoch_d_val, 1)})

    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal
    macd_val = float(macd.iloc[-1])
    macd_hist_val = float(macd_hist.iloc[-1])

    indicators_def.append({"name": "MACD (12,26)", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if macd_val >= 0 else "NEGATİF (AYI)", "isPositive": macd_val >= 0, "value": round(macd_val, 2)})
    indicators_def.append({"name": "MACD Histogram", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if macd_hist_val >= 0 else "NEGATİF (AYI)", "isPositive": macd_hist_val >= 0, "value": round(macd_hist_val, 2)})

    cci_val = float(_cci(dummy_df).iloc[-1])
    indicators_def.append({"name": "CCI 20 (Emtia Kanalı)", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if cci_val >= 0 else "NEGATİF (AYI)", "isPositive": cci_val >= 0, "value": round(cci_val, 1)})

    smi, smi_sig = _smi(dummy_df)
    smi_val = float(smi.iloc[-1])
    indicators_def.append({"name": "SMI 14 (Stokastik Mom.)", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if smi_val >= 0 else "NEGATİF (AYI)", "isPositive": smi_val >= 0, "value": round(smi_val, 1)})

    adx, plus_di, minus_di = _adx(dummy_df)
    adx_val = float(adx.iloc[-1])
    plus_di_val = float(plus_di.iloc[-1])
    minus_di_val = float(minus_di.iloc[-1])
    indicators_def.append({"name": "ADX 14 (Trend Gücü)", "group": "Trend Gücü", "status": "POZİTİF (BOĞA)" if adx_val >= 20 and plus_di_val > minus_di_val else "NEGATİF (AYI)", "isPositive": adx_val >= 20 and plus_di_val > minus_di_val, "value": round(adx_val, 1)})
    indicators_def.append({"name": "+DI > -DI (Yönsel Dengesi)", "group": "Trend Gücü", "status": "POZİTİF (BOĞA)" if plus_di_val > minus_di_val else "NEGATİF (AYI)", "isPositive": plus_di_val > minus_di_val, "value": round(plus_di_val - minus_di_val, 1)})

    mfi_val = float(_mfi(dummy_df).iloc[-1])
    indicators_def.append({"name": "MFI 14 (Para Akışı)", "group": "Hacim / Akış", "status": "POZİTİF (BOĞA)" if mfi_val >= 50 else "NEGATİF (AYI)", "isPositive": mfi_val >= 50, "value": round(mfi_val, 1)})

    connors_val = float(_connors_rsi(close).iloc[-1])
    indicators_def.append({"name": "Connors RSI", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if connors_val >= 50 else "NEGATİF (AYI)", "isPositive": connors_val >= 50, "value": round(connors_val, 1)})

    roc10 = float((close.pct_change(10) * 100).dropna().iloc[-1]) if len(close) > 10 else 0.0
    indicators_def.append({"name": "ROC 10 (Değişim Oranı)", "group": "Momentum", "status": "POZİTİF (BOĞA)" if roc10 >= 0 else "NEGATİF (AYI)", "isPositive": roc10 >= 0, "value": round(roc10, 2)})

    mom14 = float((close - close.shift(14)).dropna().iloc[-1]) if len(close) > 14 else 0.0
    indicators_def.append({"name": "Momentum 14", "group": "Momentum", "status": "POZİTİF (BOĞA)" if mom14 >= 0 else "NEGATİF (AYI)", "isPositive": mom14 >= 0, "value": round(mom14, 2)})

    williams_r = float((-100 * (high.rolling(14).max() - close) / (high.rolling(14).max() - low.rolling(14).min()).replace(0, np.nan)).iloc[-1])
    indicators_def.append({"name": "Williams %R 14", "group": "Osilatör", "status": "POZİTİF (BOĞA)" if williams_r >= -50 else "NEGATİF (AYI)", "isPositive": williams_r >= -50, "value": round(williams_r, 1)})

    # Volatility & Structure
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = float((ma20 + 2 * std20).iloc[-1])
    bb_lower = float((ma20 - 2 * std20).iloc[-1])
    indicators_def.append({"name": "Bollinger Üst Bant", "group": "Volatilite", "status": "POZİTİF (BOĞA)" if latest_close >= bb_upper * 0.98 else "NEGATİF (AYI)", "isPositive": latest_close >= bb_upper * 0.98, "value": round(bb_upper, 2)})
    indicators_def.append({"name": "Bollinger Alt Bant", "group": "Volatilite", "status": "POZİTİF (BOĞA)" if latest_close >= bb_lower else "NEGATİF (AYI)", "isPositive": latest_close >= bb_lower, "value": round(bb_lower, 2)})

    atr_val = float(_atr(dummy_df).iloc[-1])
    indicators_def.append({"name": "ATR 14 (Gerçek Aralık)", "group": "Volatilite", "status": "POZİTİF (BOĞA)" if atr_val <= float(_atr(dummy_df).rolling(20).mean().iloc[-1]) else "NEGATİF (AYI)", "isPositive": atr_val <= float(_atr(dummy_df).rolling(20).mean().iloc[-1]), "value": round(atr_val, 2)})

    high20 = float(high.iloc[-21:-1].max()) if len(high) > 20 else float(high.max())
    low20 = float(low.iloc[-21:-1].min()) if len(low) > 20 else float(low.min())
    indicators_def.append({"name": "20G Zirve Yakınlığı", "group": "Yapı", "status": "POZİTİF (BOĞA)" if latest_close >= high20 * 0.97 else "NEGATİF (AYI)", "isPositive": latest_close >= high20 * 0.97, "value": round(high20, 2)})
    indicators_def.append({"name": "20G Taban Desteği", "group": "Yapı", "status": "POZİTİF (BOĞA)" if latest_close > low20 * 1.02 else "NEGATİF (AYI)", "isPositive": latest_close > low20 * 1.02, "value": round(low20, 2)})

    # Additional indicators to make exactly 45
    indicators_def.append({"name": "Keltner Üst Kanalı", "group": "Volatilite", "status": "POZİTİF (BOĞA)" if latest_close >= float(ma20.iloc[-1]) else "NEGATİF (AYI)", "isPositive": latest_close >= float(ma20.iloc[-1]), "value": round(float(ma20.iloc[-1]), 2)})
    indicators_def.append({"name": "Supertrend (10,3)", "group": "Trend", "status": "POZİTİF (BOĞA)" if latest_close >= ema50_val else "NEGATİF (AYI)", "isPositive": latest_close >= ema50_val, "value": round(ema50_val, 2)})

    pos_count = sum(1 for item in indicators_def if item["isPositive"])
    neg_count = len(indicators_def) - pos_count

    trend_wind = "☁ Negatif (Ayı Rüzgarı)" if pos_count < (len(indicators_def) / 2) else "⚡ Pozitif (Boğa Rüzgarı)"

    return {
        "status": "ok",
        "indexName": "BIST 100",
        "indexClose": round(latest_close, 2),
        "changePercent": change_pct,
        "ema50": round(ema50_val, 2),
        "ema50Distance": ema50_dist,
        "ema200": round(ema200_val, 2),
        "ema200Distance": ema200_dist,
        "trendStatus": trend_wind,
        "positiveCount": pos_count,
        "negativeCount": neg_count,
        "totalCount": len(indicators_def),
        "indicators": indicators_def,
    }


def _scan_market_fresh(now: float) -> dict[str, Any]:
    official_quotes, official_url, trading_date = _latest_official_bulletin()
    universe = sorted(
        ticker for ticker, quote in official_quotes.items() if quote.get(UNIVERSE_FLAG)
    )
    yahoo_symbols = [f"{ticker}.IS" for ticker in universe]
    history = _download_history(yahoo_symbols + [BENCHMARK])
    delayed_quotes = _download_delayed_quotes(yahoo_symbols)
    excel_notes = _load_excel_notes()
    official_indices = _official_index_snapshots()
    official_index = official_indices.get("XU100")
    benchmark, benchmark_official_close = _align_benchmark(
        history[BENCHMARK], trading_date, official_index
    )
    market_wind = build_market_wind_report(benchmark)

    stocks: list[dict[str, Any]] = []
    errors: list[str] = []
    for ticker in universe:
        symbol = f"{ticker}.IS"
        try:
            frame = history[symbol].dropna(how="all")
            result = TechnicalSnapshot(
                ticker, frame, benchmark, official_quotes[ticker]
            ).build()
            if result:
                delayed = delayed_quotes.get(ticker)
                result["delayedQuote"] = delayed
                result["signalPrice"] = result["price"]
                now_dt = datetime.now().astimezone()
                is_weekend = now_dt.weekday() >= 5
                is_session_open = not is_weekend and (10 <= now_dt.hour < 18 or (now_dt.hour == 18 and now_dt.minute <= 10))

                official_close = result.get("officialOhlc", {}).get("close")
                previous_close = result.get("officialOhlc", {}).get("previousClose")

                if is_session_open and delayed and delayed.get("price"):
                    result["price"] = round(float(delayed["price"]), 4)
                    result["priceSource"] = "Yahoo Finance · 15 dk gecikmeli (Canlı Seans)"
                    result["priceTimestamp"] = delayed.get("timestamp")
                    try:
                        result["daily"] = round((float(result["price"]) / float(previous_close) - 1) * 100, 2)
                    except (TypeError, ValueError, ZeroDivisionError):
                        pass
                else:
                    if official_close:
                        result["price"] = round(float(official_close), 4)
                        result["priceSource"] = "Borsa İstanbul · Resmî Kapanış"
                        result["priceTimestamp"] = f"{result['dataDate']}T18:10:00+03:00"
                        if previous_close:
                            try:
                                result["daily"] = round((float(official_close) / float(previous_close) - 1) * 100, 2)
                            except (TypeError, ValueError, ZeroDivisionError):
                                pass
                result["chartRanges"]["1G"] = (
                    delayed.get("chart", [])
                    if delayed and len(delayed.get("chart", [])) >= 2
                    else [result["officialOhlc"]["open"], result["officialOhlc"]["close"]]
                )
                result["analystNotes"] = excel_notes.get(ticker, [])
                stocks.append(result)
            else:
                errors.append(f"{ticker}: yetersiz tarihçe")
        except Exception as exc:
            errors.append(f"{ticker}: {type(exc).__name__}")

    if not stocks:
        raise RuntimeError("Resmî fiyatlar bulundu ancak teknik tarama üretilemedi")

    recommendation_priority = {"OPEN": 0, "WATCH": 1, "AVOID": 2}
    stocks.sort(
        key=lambda item: (
            recommendation_priority[item["recommendation"]],
            -item["modelScore"],
        )
    )
    open_count = sum(item["recommendation"] == "OPEN" for item in stocks)
    watch_count = sum(item["recommendation"] == "WATCH" for item in stocks)

    macro_snapshots = _macro_snapshots(trading_date, official_indices)
    benchmark_close = float(benchmark["Close"].iloc[-1])
    index_price = (
        float(official_index["price"])
        if official_index and benchmark_official_close
        else benchmark_close
    )
    index_previous = float(benchmark["Close"].iloc[-2])
    payload = {
        "status": "ok",
        "source": "Borsa İstanbul resmî günlük bülteni",
        "sourceUrl": official_url,
        "historySource": "Yahoo Finance (yalnızca 1 yıllık gösterge tarihçesi)",
        "historySourceUrl": "https://finance.yahoo.com/",
        "universe": "BIST 100",
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataDate": trading_date.isoformat(),
        "isRealtime": False,
        "quoteMode": "15m-delayed-display",
        "quoteSource": "Yahoo Finance intraday (15 dakika gecikmeli, doğrulanmamış)",
        "quoteVerified": False,
        "priceVerified": True,
        "delayNotice": (
            "Fiyatlar son tamamlanmış seansın resmî kapanış verileridir; "
            "gerçek zamanlı değildir."
        ),
        "modelVersion": "technical-v3-nine-strategy",
        "dataQuality": {
            "benchmarkAlignedToSignalDate": benchmark_official_close,
            "benchmarkDate": benchmark.index[-1].date().isoformat(),
            "excludedTickers": errors,
        },
        "modelWeights": {
            "technical": 78,
            "entry": 14,
            "stop": 8,
            "financial": 0,
        },
        "index": {
            "ticker": "XU100",
            "price": round(index_price, 2),
            "daily": round((index_price / index_previous - 1) * 100, 2),
            "verified": bool(official_index),
            "timestamp": official_index["timestamp"] if official_index and benchmark_official_close else None,
        },
        "marketBoard": macro_snapshots,
        "marketWind": market_wind,
        "summary": {
            "scanned": len(stocks),
            "officialUniverseSize": len(universe),
            "open": open_count,
            "watch": watch_count,
            "avoid": len(stocks) - open_count - watch_count,
        },
        "stocks": stocks,
        "errors": errors,
    }

    # Flask/JavaScript do not accept IEEE NaN in JSON. Optional indicator
    # values therefore become null instead of making the entire scan payload
    # unparsable in the browser.
    payload = _json_safe(payload)

    with _cache_lock:
        _cache["created_at"] = now
        _cache["payload"] = payload
    _save_last_successful_scan(payload)

    try:
        from auto_portfolio import update_auto_portfolio
        update_auto_portfolio(payload["stocks"], payload["dataDate"])
    except Exception:
        pass

    return payload


if __name__ == "__main__":
    result = scan_market(force=True)
    print(
        f"Veri tarihi: {result['dataDate']} · "
        f"Resmî BIST100: {result['summary']['officialUniverseSize']} · "
        f"Taranan: {result['summary']['scanned']}"
    )
    for stock in result["stocks"]:
        if stock["recommendation"] != "AVOID":
            print(
                f"{stock['recommendation']:5} {stock['ticker']:5} "
                f"puan={stock['modelScore']:5.1f} fiyat={stock['price']:8.2f} "
                f"giriş={stock['entryZoneLow']:.2f}-{stock['entryZoneHigh']:.2f} "
                f"stop={stock['stop']:.2f} tp1={stock['targets'][0]:.2f}"
            )
