import json
import openpyxl
from pathlib import Path

# Update OGUZ_ANALIZ_ARSIVI.json with Batch 6 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch6_entries = [
    {
        "ticker": "ENDAE",
        "name": "Enda Enerji Holding A.Ş.",
        "entry_level": 15.00,
        "current_live_price": 16.71,
        "performance": "+11.40%",
        "note": "[Oğuz Telegram] Endae 15₺'ye değerse mutlaka değerlendirilebilir (%11 prim)."
    },
    {
        "ticker": "NETCD",
        "name": "Netcad Yazılım A.Ş.",
        "entry_level": 128.00,
        "current_live_price": 148.00,
        "performance": "+15.62%",
        "note": "[Oğuz Telegram] Netcd 128₺ değerlendirilebilir (148₺ tavan hareketi)."
    },
    {
        "ticker": "DOFRB",
        "name": "Dof Robotik Sanayi A.Ş.",
        "entry_level": 134.00,
        "current_live_price": 140.30,
        "performance": "+4.70%",
        "note": "[Oğuz Telegram] Dofrb 134₺ bakılabilir. 140.30₺ direnç seviyesi."
    },
    {
        "ticker": "PRKME",
        "name": "Park Elektrik Üretim Madencilik A.Ş.",
        "entry_level": 18.40,
        "current_live_price": 19.65,
        "performance": "+6.79%",
        "note": "[Oğuz Telegram / Bakır Takip] Açılışta Prkme 18,40₺ bakabilirsiniz (%9 kazanç)."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch6_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 6.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch6_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 6.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch6_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 6.")
