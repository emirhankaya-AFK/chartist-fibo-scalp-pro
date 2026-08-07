import json
import openpyxl
from pathlib import Path

# 1. Update OGUZ_ANALIZ_ARSIVI.json with Batch 2 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch2_entries = [
    {
        "ticker": "PRKAB",
        "name": "Türk Prysmian Kablo ve Sistemleri A.Ş.",
        "entry_level": 33.88,
        "current_live_price": 33.88,
        "performance": "0.00%",
        "note": "[Oğuz Telegram / Bakır Takip] Prkab 33.88₺ seviyesinden bakır kablo/maden takibi."
    },
    {
        "ticker": "CVKMD",
        "name": "CVK Maden İşletmeleri Sanayi ve Ticaret A.Ş.",
        "entry_level": 14.70,
        "current_live_price": 15.95,
        "performance": "+8.50%",
        "note": "[Oğuz Telegram / Maden Takip] Cvkmd 14,70₺ yine bakılabilir."
    },
    {
        "ticker": "AYDEM",
        "name": "Aydem Yenilenebilir Enerji A.Ş.",
        "entry_level": 23.00,
        "current_live_price": 23.82,
        "performance": "+3.56%",
        "note": "[Oğuz Telegram] Aydem 23₺ takibe alındı."
    },
    {
        "ticker": "SARKY",
        "name": "Sarkuysan Elektrolitik Bakır Sanayi A.Ş.",
        "entry_level": 23.88,
        "current_live_price": 24.80,
        "performance": "+3.85%",
        "note": "[Oğuz Telegram / Bakır Takip] Sarky 23,88₺ - 23,50₺'lere düşerse mutlaka takibe alınabilir."
    },
    {
        "ticker": "ASTOR",
        "name": "Astor Enerji A.Ş.",
        "entry_level": 288.50,
        "current_live_price": 302.75,
        "performance": "+4.94%",
        "note": "[Oğuz Telegram] Astor 288,50₺ tradelik bakılabilir. 300₺'de direnç."
    },
    {
        "ticker": "BETAE",
        "name": "Beta Enerji ve Teknoloji A.Ş.",
        "entry_level": 78.00,
        "current_live_price": 89.80,
        "performance": "+15.13%",
        "note": "[Oğuz Telegram] Betae 78₺ tradelik bakılabilir. 89.80₺ tavan takibi."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch2_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 2.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch2_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 2.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch2_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 2.")
