"""Shared commodity-to-BIST watch groups and UI snapshot helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any


COMMODITY_GROUPS = [
    {
        "name": "Altın",
        "macro_label": "ONS ALTIN ($)",
        "icon": "🟡",
        "min_move": 1.0,
        "description": "Altın ve madencilik temasına doğrudan veya kullanıcı takibine göre dolaylı bağlı hisseler.",
        "related": [
            {"ticker": "TRALT", "name": "Türk Altın İşletmeleri", "relationship": "same", "impact": "Altın fiyatına doğrudan duyarlı madencilik takibi."},
            {"ticker": "PRKAB", "name": "Türk Prysmian Kablo", "relationship": "indirect", "impact": "Kullanıcının altın grubuna eklediği dolaylı emtia takibi."},
            {"ticker": "RUZYE", "name": "RUZY Madencilik ve Enerji", "relationship": "same", "impact": "Madencilik teması nedeniyle altınla aynı yönlü takip."},
            {"ticker": "ICUGS", "name": "Işıklar Enerji", "relationship": "indirect", "impact": "Altın madenciliği temalı dolaylı takip."},
            {"ticker": "CVKMD", "name": "CVK Maden İşletmeleri", "relationship": "same", "impact": "Madencilik faaliyetleri nedeniyle aynı yönlü takip."},
            {"ticker": "KOZAL", "name": "Koza Altın", "relationship": "same", "impact": "Altın üreticisi; ons altına doğrudan duyarlı takip."},
            {"ticker": "KOZAA", "name": "Koza Anadolu", "relationship": "same", "impact": "Altın/madencilik iştiraki nedeniyle aynı yönlü takip."},
            {"ticker": "IPEKE", "name": "İpek Doğal Enerji", "relationship": "same", "impact": "Koza grubu ve madencilik bağlantısı nedeniyle takip."},
            {"ticker": "EREGL", "name": "Ereğli Demir Çelik", "relationship": "indirect", "impact": "Maden rezervi teması nedeniyle dolaylı izleme."},
        ],
    },
    {
        "name": "Gümüş",
        "macro_label": "ONS GÜMÜŞ ($)",
        "icon": "⚪",
        "min_move": 1.0,
        "description": "Değerli metal ve sanayi kullanım teması üzerinden gümüşe duyarlı takip grubu.",
        "related": [
            {"ticker": "TRALT", "name": "Türk Altın İşletmeleri", "relationship": "indirect", "impact": "Değerli metaller teması nedeniyle dolaylı takip."},
            {"ticker": "EUREN", "name": "Europen Endüstri", "relationship": "indirect", "impact": "Sanayi ve güneş paneli teması üzerinden dolaylı takip."},
            {"ticker": "SISE", "name": "Şişecam", "relationship": "indirect", "impact": "Sanayi girdileri ve cam/güneş ekosistemi üzerinden dolaylı takip."},
        ],
    },
    {
        "name": "Bakır",
        "macro_label": "BAKIR ($)",
        "icon": "🔴",
        "min_move": 1.0,
        "description": "Bakır üretimi, kablo ve metal döngüsünden etkilenebilecek hisseler.",
        "related": [
            {"ticker": "PRKME", "name": "Park Elektrik Üretim Madencilik", "relationship": "same", "impact": "Madencilik faaliyeti nedeniyle bakırla aynı yönlü takip."},
            {"ticker": "PRKAB", "name": "Türk Prysmian Kablo", "relationship": "mixed", "impact": "Bakır ana girdidir; satış fiyatı ve maliyet etkisi birlikte izlenir."},
            {"ticker": "SARKY", "name": "Sarkuysan Elektrolitik Bakır", "relationship": "mixed", "impact": "Bakır işleme faaliyeti; stok/değer artışı ile girdi maliyeti birlikte etkiler."},
            {"ticker": "KRDMD", "name": "Kardemir D", "relationship": "indirect", "impact": "Metal döngüsü üzerinden dolaylı korelasyon takibi."},
            {"ticker": "EREGL", "name": "Ereğli Demir Çelik", "relationship": "indirect", "impact": "Metal döngüsü üzerinden dolaylı korelasyon takibi."},
            {"ticker": "KCAER", "name": "Kocaer Çelik", "relationship": "indirect", "impact": "Metal ve sanayi talebi üzerinden dolaylı takip."},
        ],
    },
    {
        "name": "Brent Petrol",
        "macro_label": "BRENT PETROL ($)",
        "icon": "🛢️",
        "min_move": 1.0,
        "description": "Petrol fiyatından gelir, hammadde, lojistik veya jet yakıtı maliyetiyle etkilenebilecek hisseler.",
        "related": [
            {"ticker": "TUPRS", "name": "Tüpraş", "relationship": "mixed", "impact": "Rafineri marjı ve stok etkisi pozitif; ham petrol maliyeti ayrıca izlenir."},
            {"ticker": "PETKM", "name": "Petkim", "relationship": "inverse", "impact": "Petrol bazlı hammadde maliyeti yükselişi marj baskısı oluşturabilir."},
            {"ticker": "TRCAS", "name": "Turcas Petrol", "relationship": "mixed", "impact": "Akaryakıt ve enerji faaliyetleri nedeniyle karma etkili takip."},
            {"ticker": "FROTO", "name": "Ford Otosan", "relationship": "inverse", "impact": "Lojistik ve enerji maliyetleri nedeniyle ters/maliyet etkisi."},
            {"ticker": "THYAO", "name": "Türk Hava Yolları", "relationship": "inverse", "impact": "Jet yakıtı maliyeti nedeniyle petrol yükselişinden olumsuz etkilenebilir."},
            {"ticker": "PGSUS", "name": "Pegasus", "relationship": "inverse", "impact": "Jet yakıtı maliyeti nedeniyle petrol yükselişinden olumsuz etkilenebilir."},
        ],
    },
]


def all_group_tickers() -> list[str]:
    return sorted({item["ticker"] for group in COMMODITY_GROUPS for item in group["related"]})


def _reaction(
    commodity_daily: float | None,
    stock_daily: float | None,
    relationship: str,
) -> tuple[str, str]:
    if commodity_daily is None or stock_daily is None:
        return "Veri bekleniyor", "neutral"

    if relationship == "inverse":
        if commodity_daily >= 1.0:
            if stock_daily < 0:
                return "Maliyet baskısı görülüyor", "negative"
            return "Petrole rağmen dirençli", "positive"
        if commodity_daily <= -1.0:
            return "Maliyet rahatlaması izleniyor", "positive"
        return "Ters maliyet etkisi izleniyor", "neutral"

    if commodity_daily > 0:
        if stock_daily >= commodity_daily:
            return "Önden tepki verdi", "positive"
        if stock_daily < commodity_daily * 0.5:
            return "Emtianın gerisinde kaldı", "warning"
        return "Emtiaya paralel", "neutral"

    if commodity_daily < 0:
        if stock_daily > 0:
            return "Pozitif ayrıştı", "positive"
        if stock_daily <= commodity_daily:
            return "Emtiadan daha zayıf", "negative"
        return "Emtiaya göre dirençli", "neutral"
    return "Yatay karşılaştırma", "neutral"


def build_commodity_group_snapshot(
    scan_payload: dict[str, Any],
    commodity_rows: list[dict[str, Any]],
    delayed_quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Combine live-ish commodity rows and delayed BIST quotes for the dashboard."""
    macro_by_label = {
        item.get("label"): item
        for item in [*(scan_payload.get("marketBoard") or []), *commodity_rows]
        if item.get("label")
    }
    stocks_by_ticker = {
        str(item.get("ticker", "")).upper(): item
        for item in scan_payload.get("stocks", [])
        if item.get("ticker")
    }

    groups = []
    for definition in COMMODITY_GROUPS:
        macro = macro_by_label.get(definition["macro_label"], {})
        try:
            commodity_daily = float(macro["daily"]) if macro.get("daily") is not None else None
        except (TypeError, ValueError):
            commodity_daily = None

        members = []
        for relation in definition["related"]:
            ticker = relation["ticker"]
            stock = stocks_by_ticker.get(ticker, {})
            quote = delayed_quotes.get(ticker) or stock.get("delayedQuote") or {}
            price = quote.get("price") or stock.get("price")
            daily = quote.get("daily")
            if daily is None:
                daily = stock.get("daily")
            try:
                price = float(price) if price is not None else None
            except (TypeError, ValueError):
                price = None
            try:
                daily = float(daily) if daily is not None else None
            except (TypeError, ValueError):
                daily = None
            reaction, tone = _reaction(commodity_daily, daily, relation["relationship"])
            members.append({
                **relation,
                "price": price,
                "daily": daily,
                "timestamp": quote.get("timestamp") or stock.get("priceTimestamp"),
                "priceSource": quote.get("source") or stock.get("priceSource"),
                "modelScore": stock.get("modelScore"),
                "recommendation": stock.get("recommendation"),
                "reaction": reaction,
                "reactionTone": tone,
                "available": price is not None,
            })

        groups.append({
            "name": definition["name"],
            "label": definition["macro_label"],
            "icon": definition["icon"],
            "description": definition["description"],
            "alertThreshold": definition["min_move"],
            "commodity": {
                "value": macro.get("value"),
                "daily": commodity_daily,
                "shortChange": macro.get("shortChange"),
                "shortWindowMinutes": macro.get("shortWindowMinutes"),
                "timestamp": macro.get("timestamp"),
                "source": macro.get("source"),
            },
            "members": members,
        })

    return {
        "status": "ok",
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "stockPriceMode": "BIST yaklaşık 15 dk gecikmeli",
        "commodityPriceMode": "Emtia yaklaşık 5 dk periyotlu",
        "groups": groups,
    }
