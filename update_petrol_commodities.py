import json
import openpyxl
from pathlib import Path

# Add TUKAS and FROTO to manual_tracking.json if not present
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

for ticker in ["TUKAS", "FROTO", "TUPRS", "PETKM"]:
    if ticker not in manual_list:
        manual_list.append(ticker)

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated with Petrol group tickers.")

# Add to Excel
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    petrol_items = [
        ("TUKAS", "Tukaş Gıda Sanayi A.Ş.", 6.50, "Petrol / Akaryakıt lojistik ve tarım maliyeti takibi."),
        ("FROTO", "Ford Otosan Sanayi A.Ş.", 950.00, "Lojistik akaryakıt ve otomotiv takibi.")
    ]

    for t, name, level, note in petrol_items:
        if t not in existing_in_excel:
            ws.append([t, name, level, None, None, note, "Emtia / Petrol"])
            print(f"Added {t} to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated.")
