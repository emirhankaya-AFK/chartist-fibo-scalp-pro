import json
import openpyxl
from pathlib import Path

# Ahmet Mergen Transcript Analysis (2026)
mergen_new_data = [
    {
        "ticker": "ADES",
        "name": "Adese Alışveriş Merkezleri Ticaret A.Ş.",
        "entry_level": 0.80,
        "support": 0.35,
        "resistance": 1.20,
        "note": "[Ahmet Mergen] Kağıt 80-85 kuruş civarında. Macera gibi bir şey olabilir. Spekülatif hareketle 1.20 TL ve 2.00-3.00 TL dirençleri hedeflenebilir.",
        "source": "Mergen"
    },
    {
        "ticker": "CCOLA",
        "name": "Coca-Cola İçecek A.Ş.",
        "entry_level": 90.00,
        "support": 80.00,
        "resistance": 115.00,  # 2.33-2.40 USD equivalent
        "note": "[Ahmet Mergen] Trend pozitif. 20 haftalık hareketli ortalama ve yükselen trend desteği kırılmadıkça vagonda kalmalı. 2.33-2.40 Dolar seviyeleri ana dirençtir.",
        "source": "Mergen"
    },
    {
        "ticker": "AKBNK",
        "name": "Akbank T.A.Ş.",
        "entry_level": 67.00,
        "support": 65.00,
        "resistance": 78.00,
        "note": "[Ahmet Mergen] Akbank TOBO yapısında. 70 TL direnci aşılırsa 78-79 TL hedefi aktif olur. Stop 65.00-65.50 TL civarı konulmalı.",
        "source": "Mergen"
    },
    {
        "ticker": "BLCYT",
        "name": "Bilici Yatırım Sanayi ve Ticaret A.Ş.",
        "entry_level": 20.50,
        "support": 19.00,
        "resistance": 22.00,
        "note": "[Ahmet Mergen] Dolar bazlı tarihi dip seviyelerinde (2021 diplerine eşit). 22.00-23.70 TL geçilirse 29.00 TL çanak hedeflenebilir.",
        "source": "Mergen"
    },
    {
        "ticker": "NATEN",
        "name": "Natürel Yenilenebilir Enerji A.Ş.",
        "entry_level": 6.00,
        "support": 5.00,
        "resistance": 8.50,
        "note": "[Ahmet Mergen] Düşüş trendi sürüyor. Dolar bazlı 2022 dip seviyelerine (5.00-5.50 TL) süzülmüş durumda. Düşüşün durması için 50 haftalık HO üzerine geçilmeli.",
        "source": "Mergen"
    }
]

# 1. Update manual_tracking.json
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for entry in mergen_new_data:
    if entry["ticker"] not in manual_list:
        manual_list.append(entry["ticker"])

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with new Mergen levels.")

# 2. Update Hisselerin_Teknik_Verileri.xlsx
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active

    # Gather existing tickers in excel
    existing_in_excel = {}
    for r in range(2, ws.max_row + 1):
        val = ws.cell(row=r, column=1).value
        if val:
            existing_in_excel[str(val).strip().upper()] = r

    for entry in mergen_new_data:
        t = entry["ticker"]
        if t in existing_in_excel:
            row_idx = existing_in_excel[t]
            ws.cell(row=row_idx, column=3, value=entry["entry_level"])
            ws.cell(row=row_idx, column=6, value=entry["note"])
            ws.cell(row=row_idx, column=7, value="Mergen")
            print(f"Updated existing {t} in Excel at row {row_idx}.")
        else:
            ws.append([t, entry["name"], entry["entry_level"], entry["support"], entry["resistance"], entry["note"], "Mergen"])
            print(f"Added new {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated successfully.")
