import json
import openpyxl
from pathlib import Path

# Update OGUZ_ANALIZ_ARSIVI.json with Batch 3 screenshot calls
oguz_archive_file = Path("OGUZ_ANALIZ_ARSIVI.json")
with open(oguz_archive_file, "r", encoding="utf-8") as f:
    oguz_data = json.load(f)

batch3_entries = [
    {
        "ticker": "ZGYO",
        "name": "Zergay Gayrimenkul Yatırım Ortaklığı A.Ş.",
        "entry_level": 33.90,
        "current_live_price": 33.90,
        "performance": "0.00%",
        "note": "[Oğuz Telegram] Zgyo 33.90₺ takibe alındı."
    },
    {
        "ticker": "EKDMR",
        "name": "Ege Demir Sanayi A.Ş.",
        "entry_level": 47.74,
        "current_live_price": 47.74,
        "performance": "0.00%",
        "note": "[Oğuz Telegram] Ekdmr 47.74₺ takibe alındı."
    },
    {
        "ticker": "MEYSU",
        "name": "Meysu Gıda Sanayi A.Ş.",
        "entry_level": 10.99,
        "current_live_price": 10.99,
        "performance": "0.00%",
        "note": "[Oğuz Telegram] Meysu 10.99₺ takibe alındı."
    },
    {
        "ticker": "PENGD",
        "name": "Penguen Gıda Sanayi A.Ş.",
        "entry_level": 9.60,
        "current_live_price": 9.79,
        "performance": "+1.98%",
        "note": "[Oğuz Telegram] Pengd 9,60₺ yine bakılabilir 9₺ dibi göz önünde tutularak."
    },
    {
        "ticker": "PAHOL",
        "name": "Pasifik Holding A.Ş.",
        "entry_level": 1.27,
        "current_live_price": 1.40,
        "performance": "+10.24%",
        "note": "[Oğuz Telegram] Pahol 1,27₺ tavan takibi."
    },
    {
        "ticker": "KTLEV",
        "name": "Katılımevim Tasarruf Finansman A.Ş.",
        "entry_level": 37.28,
        "current_live_price": 41.52,
        "performance": "+11.37%",
        "note": "[Oğuz Telegram] Ktlev alabilir (Tabandan %16 tepki)."
    },
    {
        "ticker": "PASEU",
        "name": "Pasifik Avrasya Lojistik Dış Ticaret A.Ş.",
        "entry_level": 94.00,
        "current_live_price": 94.00,
        "performance": "0.00%",
        "note": "[Oğuz Telegram] Paseu 94₺, 90₺'de ekleme yapacak şekilde değerlendiriyorum."
    },
    {
        "ticker": "JANTS",
        "name": "Jantsa Jant Sanayi ve Ticaret A.Ş.",
        "entry_level": 14.85,
        "current_live_price": 15.66,
        "performance": "+5.45%",
        "note": "[Oğuz Telegram] Jants 14,85₺ açılışta bakabiliriz 14,50₺ altı. 16₺ direnç."
    }
]

existing_tickers = {item["ticker"]: i for i, item in enumerate(oguz_data)}
for entry in batch3_entries:
    if entry["ticker"] in existing_tickers:
        oguz_data[existing_tickers[entry["ticker"]]] = entry
    else:
        oguz_data.append(entry)

with open(oguz_archive_file, "w", encoding="utf-8") as f:
    json.dump(oguz_data, f, ensure_ascii=False, indent=2)

print("✅ OGUZ_ANALIZ_ARSIVI.json updated with Batch 3.")

# 2. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in batch3_entries:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Batch 3.")

# 3. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    for entry in batch3_entries:
        t = entry["ticker"]
        if t not in existing_in_excel:
            ws.append([t, entry["name"], entry["entry_level"], None, None, entry["note"], "Oğuz"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated with Batch 3.")
