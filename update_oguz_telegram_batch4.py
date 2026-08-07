import json
import openpyxl
from pathlib import Path

# Update OGUZ_ANALIZ_ARSIVI.json with Batch 4 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch4_entries = [
    {
        "ticker": "ARFYE",
        "name": "Arf Bio Enerji Sanayi A.Ş.",
        "entry_level": 29.20,
        "current_live_price": 29.20,
        "performance": "0.00%",
        "note": "[Oğuz Telegram] Arfye 29.20₺ takibe alındı."
    },
    {
        "ticker": "INVEO",
        "name": "Inveo Yatırım Holding A.Ş.",
        "entry_level": 6.98,
        "current_live_price": 7.11,
        "performance": "+1.86%",
        "note": "[Oğuz Telegram] Inveo 6,98₺. Lakin 6,80 civarında stop olunabilir."
    },
    {
        "ticker": "MIATK",
        "name": "Mia Teknoloji A.Ş.",
        "entry_level": 29.84,
        "current_live_price": 30.08,
        "performance": "+0.80%",
        "note": "[Oğuz Telegram] Miatk 29,84₺ tradelik bakılabilir (%1-2 marj)."
    },
    {
        "ticker": "EKDMR",
        "name": "Ekinciler Demir ve Çelik Sanayi A.Ş.",
        "entry_level": 48.40,
        "current_live_price": 49.20,
        "performance": "+1.65%",
        "note": "[Oğuz Telegram] Ekdmr 48,40₺ / 49.00₺ tekrar tradelik bakılabilir."
    },
    {
        "ticker": "YAYLA",
        "name": "Yayla Enerji Üretim Turizm A.Ş.",
        "entry_level": 20.90,
        "current_live_price": 22.34,
        "performance": "+6.89%",
        "note": "[Oğuz Telegram] Yayla 20,90₺ tradelik bakabiliriz (%7 prim)."
    },
    {
        "ticker": "NETCD",
        "name": "Netcad Yazılım A.Ş.",
        "entry_level": 126.40,
        "current_live_price": 128.40,
        "performance": "+1.58%",
        "note": "[Oğuz Telegram] Netcd 126,40₺ tradelik takip edilebilir."
    },
    {
        "ticker": "LOGO",
        "name": "Logo Yazılım Sanayi ve Ticaret A.Ş.",
        "entry_level": 133.90,
        "current_live_price": 139.60,
        "performance": "+4.26%",
        "note": "[Oğuz Telegram] Logo 133,90₺ buradan takip ediyorum (%5 kazanç)."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch4_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 4.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch4_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 4.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch4_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 4.")
