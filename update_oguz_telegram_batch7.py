import json
import openpyxl
from pathlib import Path

# Update OGUZ_ANALIZ_ARSIVI.json with Batch 7 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch7_entries = [
    {
        "ticker": "ICUGS",
        "name": "İşıklar Enerji ve Yapı Holding A.Ş.",
        "entry_level": 5.42,
        "current_live_price": 5.42,
        "performance": "0.00%",
        "note": "[Oğuz Telegram / Altın Madenciliği] İcugs 5,42₺. Altın madenciliği faaliyetleri var, takibe alınabilir."
    },
    {
        "ticker": "EKDMR",
        "name": "Ekinciler Demir ve Çelik Sanayi A.Ş.",
        "entry_level": 47.30,
        "current_live_price": 46.74,
        "performance": "-1.18%",
        "note": "[Oğuz Telegram] Ekdmr 47,30₺ bakılabilir."
    },
    {
        "ticker": "ARFYE",
        "name": "Arf Bio Enerji Sanayi A.Ş.",
        "entry_level": 29.00,
        "current_live_price": 32.50,
        "performance": "+12.07%",
        "note": "[Oğuz Telegram] Arfye 29₺ takibi (%14 kazanç)."
    },
    {
        "ticker": "CWENE",
        "name": "Cw Enerji Mühendislik A.Ş.",
        "entry_level": 200.00,
        "current_live_price": 280.00,
        "performance": "+40.00%",
        "note": "[Oğuz Telegram] Cwene %40 prim takibi."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch7_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 7.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch7_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 7.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch7_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 7.")
