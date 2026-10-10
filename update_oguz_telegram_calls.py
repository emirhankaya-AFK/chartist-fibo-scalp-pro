import json
import openpyxl
from pathlib import Path

# 1. Update OGUZ_ANALIZ_ARSIVI.json
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

new_entries = [
    {
        "ticker": "AKFYE",
        "name": "Akfen Yenilenebilir Enerji A.Ş.",
        "entry_level": 23.20,
        "current_live_price": 24.38,
        "performance": "+5.08%",
        "note": "[Oğuz Telegram] Buna 23₺'de 23,40₺ ortalama yapabilir. 24.50₺ direnç."
    },
    {
        "ticker": "PRKME",
        "name": "Park Elektrik Üretim Madencilik A.Ş.",
        "entry_level": 17.84,
        "current_live_price": 19.11,
        "performance": "+7.12%",
        "note": "[Oğuz Telegram] Alıp satanlar Prkme 17,84₺ bakabilir. Bakır ve Madencilik takibi."
    },
    {
        "ticker": "BETAE",
        "name": "Beta Enerji ve Teknoloji A.Ş.",
        "entry_level": 78.00,
        "current_live_price": 108.60,
        "performance": "+39.23%",
        "note": "[Oğuz Telegram] Betae 78₺ tradelik bakılabilir."
    },
    {
        "ticker": "NETCD",
        "name": "Netcad Yazılım A.Ş.",
        "entry_level": 128.00,
        "current_live_price": 140.50,
        "performance": "+9.77%",
        "note": "[Oğuz Telegram] Netcd 128₺ buradan değerlendirilebilir (%10+ marj)."
    },
    {
        "ticker": "ENERY",
        "name": "Enerya Enerji A.Ş.",
        "entry_level": 8.86,
        "current_live_price": 11.20,
        "performance": "+26.41%",
        "note": "[Oğuz Telegram] Enery 8,86₺ buradan değerlendiriyorum."
    },
    {
        "ticker": "TRALT",
        "name": "Türk Altın İşletmeleri A.Ş.",
        "entry_level": 12.00,
        "current_live_price": 12.45,
        "performance": "+3.75%",
        "note": "[Oğuz Telegram / Emtia Takip] Altın emtiasına duyarlı altın madenciliği takibi."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in new_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated cleanly.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in new_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated cleanly.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    # Add new rows to Excel sheet
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in new_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated cleanly.")
