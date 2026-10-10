from __future__ import annotations

import json
from pathlib import Path

import openpyxl


SOURCE_TAG = "[Ahmet Mergen][2026-08-11 Transcript]"
BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "Hisselerin_Teknik_Verileri.xlsx"
TRACKING_PATH = BASE_DIR / "manual_tracking.json"
ARCHIVE_PATH = BASE_DIR / "AHMET_MERGEN_ANALIZ_ARSIVI.json"


ANALYSES = [
    {
        "analysis_id": "mergen-20260811-xu100",
        "ticker": "XU100",
        "name": "BIST 100 Endeksi",
        "entry_level": 13960.0,
        "support": None,
        "resistance": 14254.0,
        "note": f"{SOURCE_TAG} 13.958-13.960 üzeri hareket 14.250-14.254 direncini gündeme getirir. 14.254 kırılırsa 14.630, 14.876 ve 15.204; devamında 17.200-17.500 puanlık büyük çanak hedefi izlenebilir. Zaman: 00:00:13-00:04:32.",
    },
    {
        "analysis_id": "mergen-20260811-yigit",
        "ticker": "YIGIT",
        "name": "Yiğit Akü Malzemeleri Nakliyat Sanayi A.Ş.",
        "entry_level": None,
        "support": None,
        "resistance": 28.0,
        "note": f"{SOURCE_TAG} 28-29 TL bölgesinde tıkanma var. Otomotiv sektörü zayıf olduğu için direnç aşılmadan güçlü hareket teyit edilmiş sayılmıyor. Zaman: 00:06:03-00:06:50.",
    },
    {
        "analysis_id": "mergen-20260811-sasa",
        "ticker": "SASA",
        "name": "Sasa Polyester Sanayi A.Ş.",
        "entry_level": 25.0,
        "support": 20.36,
        "resistance": 29.0,
        "note": f"{SOURCE_TAG} 20,36-21,50 TL dip bölgesi. 20 TL altı zayıflama riski; 25 TL üzeri 29 TL'yi, 30 TL üzeri 39-40 TL eski tepe bölgesini gündeme getirir. Uzun vadeli ortalamaların altında olduğu için teyit beklenmeli. Zaman: 00:06:50-00:10:28 ve 00:32:50-00:37:19.",
    },
    {
        "analysis_id": "mergen-20260811-yayla",
        "ticker": "YAYLA",
        "name": "Yayla Agro Gıda Sanayi ve Ticaret A.Ş.",
        "entry_level": 11.0,
        "support": 10.0,
        "resistance": 12.5,
        "note": f"{SOURCE_TAG} 11 TL haftalık ortalama/teyit seviyesi. Birkaç kapanış 11 TL üzerinde kalırsa 12,50 ve 14-14,50 TL; devamında 15-16 TL potansiyeli değerlendirilebilir. Zaman: 00:11:45-00:14:23.",
    },
    {
        "analysis_id": "mergen-20260811-bobet",
        "ticker": "BOBET",
        "name": "Boğaziçi Beton Sanayi ve Ticaret A.Ş.",
        "entry_level": 18.0,
        "support": 17.5,
        "resistance": 20.5,
        "note": f"{SOURCE_TAG} 17,50-18 TL çoklu dip/tepki bölgesi. 16,50-16,75 TL altı stop düşünülebilir. 20,50-21 TL aşılırsa 24-24,20 TL; daha sonra 28,50-29 TL hedef/direnç bölgesi. Zaman: 00:14:56-00:19:52.",
    },
    {
        "analysis_id": "mergen-20260811-cvkmd",
        "ticker": "CVKMD",
        "name": "CVK Maden İşletmeleri Sanayi ve Ticaret A.Ş.",
        "entry_level": 15.0,
        "support": 14.75,
        "resistance": 18.5,
        "note": f"{SOURCE_TAG} 14,75-15 TL 20 haftalık ortalama/stop bölgesi; kırılırsa 12,50 TL 50 haftalık ortalama desteği izlenir. 18-18,50 TL sıkışma direnci aşılırsa 21,50-22 TL ve 25 TL hedefleri gündeme gelir. Zaman: 00:19:52-00:24:28.",
    },
    {
        "analysis_id": "mergen-20260811-froto",
        "ticker": "FROTO",
        "name": "Ford Otomotiv Sanayi A.Ş.",
        "entry_level": None,
        "support": 62.0,
        "resistance": None,
        "note": f"{SOURCE_TAG} Endeks değişikliği kaynaklı yabancı fon satış baskısı vurgulandı. Mevcut dip bölgesi korunmazsa 62 TL derin destek/alım için yeniden değerlendirme seviyesi olarak belirtildi. Zaman: 00:25:21-00:32:50.",
    },
    {
        "analysis_id": "mergen-20260811-halkb",
        "ticker": "HALKB",
        "name": "Türkiye Halk Bankası A.Ş.",
        "entry_level": None,
        "support": None,
        "resistance": None,
        "note": f"{SOURCE_TAG} Bedelli/sermaye işlemi belirsizliğiyle satış baskısı ve bankacılık endeksi desteğinin kritik olduğu belirtildi. İkili tepe senaryosundaki 40 cent hedef teknik ölçüm olarak anlatıldı, kesin beklenti olarak sunulmadı. Zaman: 00:37:19-00:40:35.",
    },
    {
        "analysis_id": "mergen-20260811-xbank",
        "ticker": "XBANK",
        "name": "BIST Banka Endeksi",
        "entry_level": None,
        "support": None,
        "resistance": None,
        "note": f"{SOURCE_TAG} Bankacılık endeksi uzun vadeli ortalama ve dip trend çizgisinde bıçak sırtında. Büyük bankalarda ortak satış sürerse genel endeks senaryosunun bozulacağı vurgulandı. Dolar bazlı 300-365 seviyeleri yorumlandığı için TL alarmı oluşturulmadı. Zaman: 00:39:37-00:42:23.",
    },
    {
        "analysis_id": "mergen-20260811-ulker",
        "ticker": "ULKER",
        "name": "Ülker Bisküvi Sanayi A.Ş.",
        "entry_level": 85.0,
        "support": 85.0,
        "resistance": 100.0,
        "note": f"{SOURCE_TAG} Yaklaşık 85 TL/1,90 USD bölgesinde tarihsel diplerin altına sarkma var. BIST 14.250'yi büyük hisselerle geçmeden alım için acele edilmemesi; tepki halinde 100 TL ortalama bölgesinin izlenmesi söylendi. Zaman: 00:44:34-00:50:13.",
    },
    {
        "analysis_id": "mergen-20260811-naten",
        "ticker": "NATEN",
        "name": "Natürel Yenilenebilir Enerji A.Ş.",
        "entry_level": None,
        "support": 5.0,
        "resistance": 6.5,
        "note": f"{SOURCE_TAG} Dolar bazında 2022 diplerinin de altı ve yaklaşık 10 cent bölgesi. Çok düşmüş olsa da trend hâlâ negatif; 6,50 TL ve ardından 7,50 TL haftalık ortalamaları aşmadan teyit yok. Zaman: 00:50:13-00:53:02.",
    },
    {
        "analysis_id": "mergen-20260811-tavhl",
        "ticker": "TAVHL",
        "name": "TAV Havalimanları Holding A.Ş.",
        "entry_level": 300.0,
        "support": 250.0,
        "resistance": 300.0,
        "note": f"{SOURCE_TAG} Ana yatay bant 200-300 TL. 250 TL altı yeniden zayıflama, 215 TL derin destek; 300 TL üzerinde tutunma alıcı teyidi olarak değerlendirilebilir. Petrol yükselişi havacılık için risk. Zaman: 00:53:50-00:56:44.",
    },
    {
        "analysis_id": "mergen-20260811-glrmk",
        "ticker": "GLRMK",
        "name": "Gülermak Ağır Sanayi İnşaat ve Taahhüt A.Ş.",
        "entry_level": None,
        "support": 150.0,
        "resistance": 210.0,
        "note": f"{SOURCE_TAG} 260 TL sonrası düşüşte 150-210 TL yatay bandı. Sağ omuz oluşumu tamamlanırsa TOBO ile yeniden 200 TL üzeri/210 TL tepe bölgesi gündeme gelebilir. Zaman: 01:07:25-01:08:58.",
    },
    {
        "analysis_id": "mergen-20260811-brent",
        "ticker": "BZ=F",
        "name": "Brent Petrol ($)",
        "entry_level": None,
        "support": 80.0,
        "resistance": 90.75,
        "note": f"{SOURCE_TAG} 90,61-90,75 dolar boşluk/ilk direnç. 95-96 dolar enflasyon ve faiz riski; 98 dolar kırılırsa 115-116 dolar teknik hedef senaryosu. 80 dolar altı yeniden zayıflama. Zaman: 00:59:38-01:03:23.",
    },
    {
        "analysis_id": "mergen-20260811-gold",
        "ticker": "GC=F",
        "name": "Ons Altın ($)",
        "entry_level": None,
        "support": 4200.0,
        "resistance": 4600.0,
        "note": f"{SOURCE_TAG} 4.382 dolar civarı kâr alma bölgesi olarak değerlendirildi. 4.000-4.200 dolar ortalama/destek alanı; trend korunursa 4.600 dolar civarında yeniden satıcı bekleniyor. Petrol 95-96 dolara giderse 4.200'e düzeltme riski. Zaman: 01:03:23-01:05:01.",
    },
    {
        "analysis_id": "mergen-20260811-silver",
        "ticker": "SI=F",
        "name": "Ons Gümüş ($)",
        "entry_level": 65.0,
        "support": 64.0,
        "resistance": 71.0,
        "note": f"{SOURCE_TAG} 64-65 dolar kırılımı ve yaklaşan golden cross pozitif. Teknik hedef/direnç 71 dolar; hızlı yükseliş sonrasında düzeltme riskine karşı stoplu izlenmeli. Zaman: 01:05:01-01:07:25.",
    },
    {
        "analysis_id": "mergen-20260811-taten",
        "ticker": "TATEN",
        "name": "Tatlıpınar Enerji Üretim A.Ş.",
        "entry_level": 6.75,
        "support": 6.5,
        "resistance": 21.0,
        "note": f"{SOURCE_TAG} 6,50-7,00 TL geçmiş dip/tepki bölgesi olarak izleniyor; mali görünüm zayıf olduğu için yalnızca destek üzerinde tutunma ve en az 1-2 hafta teyit sonrası değerlendirme yapılmalı. 21 TL güçlü satış/direnç bölgesi. 5 TL video seviyesi değildir; 5 TL'ye sarkma 6,50-7,00 desteğinin kırıldığı risk senaryosudur. Zaman: 00:22:47-00:24:35.",
    },
    {
        "analysis_id": "mergen-20260811-thyao",
        "ticker": "THYAO",
        "name": "Türk Hava Yolları A.O.",
        "entry_level": 315.0,
        "support": 310.0,
        "resistance": 325.0,
        "note": f"{SOURCE_TAG} 315 TL üzeri toparlanma 325 TL'yi; formasyon teyidiyle yaklaşık 355 TL hedefini gündeme getirir. 310 TL altı kısa vadeli stop/bozulma seviyesi olarak takip edilmeli. Zaman: 00:15:39-00:18:55.",
    },
]


ALERTS = [
    ("XU100", "BIST 100 Endeksi", ">=", 13960.0, "13.960 üzeri 14.250-14.254 hareketi tetiklenebilir."),
    ("XU100", "BIST 100 Endeksi", ">=", 14254.0, "Ana direnç kırılımı; 14.630 ve 14.876 hedefleri izlenir."),
    ("XU100", "BIST 100 Endeksi", ">=", 14630.0, "İlk üst hedef görüldü."),
    ("XU100", "BIST 100 Endeksi", ">=", 14876.0, "İkinci üst hedef görüldü."),
    ("XU100", "BIST 100 Endeksi", ">=", 15204.0, "TOBO/çanak hedef bölgesi görüldü."),
    ("YIGIT.IS", "Yiğit Akü", ">=", 28.0, "28-29 TL direnç bölgesine geldi."),
    ("SASA.IS", "Sasa Polyester", "<=", 20.0, "20 TL altı zayıflama riski."),
    ("SASA.IS", "Sasa Polyester", ">=", 25.0, "25 TL üzeri 29 TL potansiyeli."),
    ("SASA.IS", "Sasa Polyester", ">=", 29.0, "29 TL yatay bant direnci."),
    ("SASA.IS", "Sasa Polyester", ">=", 30.0, "30 TL üzeri 39-40 TL eski tepe senaryosu."),
    ("YAYLA.IS", "Yayla Agro Gıda", ">=", 11.0, "Haftalık ortalama/teyit seviyesi."),
    ("YAYLA.IS", "Yayla Agro Gıda", ">=", 12.5, "İlk hedef görüldü; 14-14,50 izlenir."),
    ("YAYLA.IS", "Yayla Agro Gıda", ">=", 14.5, "İkinci hedef/direnç görüldü."),
    ("BOBET.IS", "Boğaziçi Beton", "<=", 18.0, "17,50-18 TL çoklu dip/tepki bölgesi."),
    ("BOBET.IS", "Boğaziçi Beton", "<=", 16.75, "Analistin belirttiği stop bölgesi."),
    ("BOBET.IS", "Boğaziçi Beton", ">=", 20.5, "20,50-21 TL ilk direnç."),
    ("BOBET.IS", "Boğaziçi Beton", ">=", 24.0, "24-24,20 TL hedef/direnç."),
    ("BOBET.IS", "Boğaziçi Beton", ">=", 28.5, "28,50-29 TL üst hedef."),
    ("CVKMD.IS", "CVK Maden", "<=", 14.75, "20 haftalık ortalama/stop bölgesi."),
    ("CVKMD.IS", "CVK Maden", "<=", 12.5, "50 haftalık ortalama desteği."),
    ("CVKMD.IS", "CVK Maden", ">=", 18.5, "Sıkışma direnci; kırılımda 21,50-22 ve 25 hedefleri."),
    ("CVKMD.IS", "CVK Maden", ">=", 21.5, "İlk üst hedef bölgesi."),
    ("CVKMD.IS", "CVK Maden", ">=", 25.0, "Ana teknik hedef."),
    ("FROTO.IS", "Ford Otosan", "<=", 62.0, "Derin destek/yeniden değerlendirme seviyesi."),
    ("ULKER.IS", "Ülker Bisküvi", "<=", 85.0, "Tarihsel dip bölgesi."),
    ("ULKER.IS", "Ülker Bisküvi", ">=", 100.0, "Tepki hedefi/ortalama bölgesi."),
    ("NATEN.IS", "Natürel Enerji", "<=", 5.0, "Aşırı düşüş/dip bölgesi; trend teyidi yok."),
    ("NATEN.IS", "Natürel Enerji", ">=", 6.5, "İlk haftalık ortalama/teyit seviyesi."),
    ("NATEN.IS", "Natürel Enerji", ">=", 7.5, "İkinci haftalık ortalama/teyit seviyesi."),
    ("TAVHL.IS", "TAV Havalimanları", "<=", 250.0, "250 TL altı zayıflama."),
    ("TAVHL.IS", "TAV Havalimanları", "<=", 215.0, "Derin destek bölgesi."),
    ("TAVHL.IS", "TAV Havalimanları", ">=", 300.0, "300 TL üzerinde tutunma alıcı teyidi."),
    ("GLRMK.IS", "Gülermak Ağır Sanayi", "<=", 150.0, "150-210 TL yatay bandın alt sınırı."),
    ("GLRMK.IS", "Gülermak Ağır Sanayi", ">=", 210.0, "TOBO ihtimalinde tepe/direnç bölgesi."),
    ("BZ=F", "Brent Petrol", "<=", 80.0, "80 dolar altı zayıflama."),
    ("BZ=F", "Brent Petrol", ">=", 90.75, "90,61-90,75 dolar boşluk/direnç bölgesi."),
    ("BZ=F", "Brent Petrol", ">=", 96.0, "Enflasyon ve faiz riski artan kritik bölge."),
    ("BZ=F", "Brent Petrol", ">=", 98.0, "Kırılımda 115-116 dolar teknik hedef senaryosu."),
    ("GC=F", "Ons Altın", "<=", 4200.0, "Ortalama/destek ve trend kontrol bölgesi."),
    ("GC=F", "Ons Altın", ">=", 4600.0, "Kâr satışı beklenen hedef/direnç bölgesi."),
    ("SI=F", "Ons Gümüş", ">=", 65.0, "64-65 dolar kırılım teyidi."),
    ("SI=F", "Ons Gümüş", ">=", 71.0, "Teknik hedef/direnç bölgesi."),
    ("TATEN.IS", "Tatlıpınar Enerji", "<=", 6.5, "6,50-7 TL geçmiş dip/tepki bölgesi; mali teyit olmadan alım sinyali değildir."),
    ("TATEN.IS", "Tatlıpınar Enerji", "<=", 5.0, "6,50-7 TL desteği kırılmış olur; tepki garantisi değil, yüksek risk/izleme alarmı."),
    ("TATEN.IS", "Tatlıpınar Enerji", ">=", 21.0, "Güçlü satış/direnç bölgesi; kâr realizasyonu değerlendirilebilir."),
    ("THYAO.IS", "Türk Hava Yolları", ">=", 315.0, "315 TL üzeri toparlanma teyidi; 325 TL izlenir."),
    ("THYAO.IS", "Türk Hava Yolları", "<=", 310.0, "Kısa vadeli stop/bozulma seviyesi."),
    ("THYAO.IS", "Türk Hava Yolları", ">=", 355.0, "Formasyon hedef bölgesi."),
]


def update_archive() -> None:
    existing = []
    if ARCHIVE_PATH.exists():
        existing = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    by_id = {row.get("analysis_id"): row for row in existing if row.get("analysis_id")}
    for row in ANALYSES:
        by_id[row["analysis_id"]] = {**row, "source": "Ahmet Mergen"}
    ARCHIVE_PATH.write_text(
        json.dumps(list(by_id.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_tracking() -> None:
    tracked = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    stock_tickers = {
        row["ticker"]
        for row in ANALYSES
        if "=" not in row["ticker"] and row["ticker"] not in {"XU100", "XBANK"}
    }
    for ticker in sorted(stock_tickers):
        if ticker not in tracked:
            tracked.append(ticker)
    TRACKING_PATH.write_text(
        json.dumps(tracked, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_excel() -> None:
    workbook = openpyxl.load_workbook(EXCEL_PATH)
    tracking_sheet = workbook["BIST Takip Listesi"]
    existing_ids = {
        str(tracking_sheet.cell(row=row, column=1).value).strip(): row
        for row in range(4, tracking_sheet.max_row + 1)
        if tracking_sheet.cell(row=row, column=1).value
    }
    for item in ANALYSES:
        row_id = item["analysis_id"]
        row = existing_ids.get(row_id) or tracking_sheet.max_row + 1
        values = [
            row_id,
            item["ticker"],
            item["name"],
            item["entry_level"],
            item["support"],
            item["resistance"],
            None,
            item["note"],
        ]
        for column, value in enumerate(values, start=1):
            tracking_sheet.cell(row=row, column=column, value=value)

    alarm_sheet = workbook["Aktif Alarmlar (Premium)"]
    existing_alerts = {}
    for row in range(4, alarm_sheet.max_row + 1):
        note = str(alarm_sheet.cell(row=row, column=7).value or "")
        if SOURCE_TAG not in note:
            continue
        key = (
            str(alarm_sheet.cell(row=row, column=1).value or "").upper(),
            float(alarm_sheet.cell(row=row, column=4).value),
            str(alarm_sheet.cell(row=row, column=3).value or ""),
        )
        existing_alerts[key] = row

    for symbol, name, operator, target, detail in ALERTS:
        rule = f"Fiyat {operator} Hedef"
        key = (symbol.upper(), float(target), rule)
        row = existing_alerts.get(key) or alarm_sheet.max_row + 1
        values = [
            symbol,
            name,
            rule,
            target,
            "Evet",
            "Bekliyor",
            f"{SOURCE_TAG} {detail}",
        ]
        for column, value in enumerate(values, start=1):
            alarm_sheet.cell(row=row, column=column, value=value)

    workbook.save(EXCEL_PATH)


if __name__ == "__main__":
    update_archive()
    update_tracking()
    update_excel()
    print(f"Saved {len(ANALYSES)} non-crypto analyses and {len(ALERTS)} active levels.")
