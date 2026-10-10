import json
import openpyxl
from pathlib import Path

# Update OGUZ_ANALIZ_ARSIVI.json with Batch 5 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch5_entries = [
    {
        "ticker": "ECOGR",
        "name": "Ecogreen Enerji Holding A.Ş.",
        "entry_level": 34.40,
        "current_live_price": 36.32,
        "performance": "+5.58%",
        "note": "[Oğuz Telegram] Ecogr 34,40₺ trade verebilir."
    },
    {
        "ticker": "SDTTR",
        "name": "SDT Uzay ve Savunma Teknolojileri A.Ş.",
        "entry_level": 216.00,
        "current_live_price": 225.80,
        "performance": "+4.54%",
        "note": "[Oğuz Telegram] Sdttr 216₺, 190₺ dibi var. Buradan değerlendirilebilir."
    },
    {
        "ticker": "FONET",
        "name": "Fonet Bilgi Teknolojileri A.Ş.",
        "entry_level": 5.00,
        "current_live_price": 5.26,
        "performance": "+5.20%",
        "note": "[Oğuz Telegram] Fonet 5₺ buradan tradelik bakılabilir."
    },
    {
        "ticker": "ARFYE",
        "name": "Arf Bio Enerji Sanayi A.Ş.",
        "entry_level": 29.20,
        "current_live_price": 29.82,
        "performance": "+2.12%",
        "note": "[Oğuz Telegram] Arfye 29,20₺ Güzel tepki verebilir."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch5_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 5.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch5_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 5.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch5_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 5.")
