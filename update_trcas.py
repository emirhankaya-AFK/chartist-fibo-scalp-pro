import json
import openpyxl
from pathlib import Path

# Add TRCAS to manual_tracking.json and remove TUKAS
tracking_file = Path("manual_tracking.json")
with open(tracking_file, "r", encoding="utf-8") as f:
    manual_list = json.load(f)

if "TUKAS" in manual_list:
    manual_list.remove("TUKAS")

if "TRCAS" not in manual_list:
    manual_list.append("TRCAS")

with open(tracking_file, "w", encoding="utf-8") as f:
    json.dump(manual_list, f, ensure_ascii=False, indent=2)

print("✅ manual_tracking.json updated: TRCAS added, TUKAS removed.")

# Update Excel
excel_file = Path("Hisselerin_Teknik_Verileri.xlsx")
if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file)
    ws = wb.active
    existing_in_excel = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            existing_in_excel.add(str(row[0]).strip().upper())

    if "TRCAS" not in existing_in_excel:
        ws.append(["TRCAS", "Turcas Petrol A.Ş.", 28.50, None, None, "Petrol, Akaryakıt Dağıtım ve Enerji takibi.", "Emtia / Petrol"])
        print("Added TRCAS to Excel.")

    wb.save(excel_file)
    print("✅ Hisselerin_Teknik_Verileri.xlsx updated.")
