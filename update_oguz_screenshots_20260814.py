import json
from pathlib import Path

path = Path(__file__).with_name("OGUZ_ANALIZ_ARSIVI.json")
rows = json.loads(path.read_text(encoding="utf-8"))
updates = {
    "AYDEM": {"entry_level": 23.0, "current_live_price": 25.74, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] AYDEM 23 TL takip seviyesi. Tutan varsa şirket ilişkileri ve bilanço açıklaması nedeniyle değerlendirme notu."},
    "SDTTR": {"entry_level": 216.0, "support": 190.0, "current_live_price": 255.50, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] SDTTR 216 TL takip seviyesi; 190 TL geçmiş dip/destek olarak belirtilmiş, bu bölgeden değerlendirme notu."},
    "ATATR": {"entry_level": 14.06, "current_live_price": 14.94, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] ATATR 14,06 TL seviyesiyle kısa vadeli izleme notu. Görseldeki devam eden hedef metni kesik olduğu için kesin hedef eklenmedi."},
    "OBASE": {"entry_level": 39.0, "current_live_price": 39.72, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] OBASE 39 TL takip seviyesi."},
    "YAYLA": {"entry_level": 21.20, "current_live_price": 25.14, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] YAYLA 21,20 TL takip seviyesi; 25,14 TL ekranda görüldü. Görselde kısa vadede %20 notu var; yüzde TL direnç kabul edilmedi."},
    "KRONT": {"entry_level": 18.0, "current_live_price": None, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz][2026-06-02] KRONT 18 TL seviyesinden yapay zekâ alanında çalışan şirket olarak takip ediliyor; ekranda tutan eden varsa değerlendirecek notu."},
    "NETCD": {"entry_level": 136.50, "resistance": 145.0, "current_live_price": 142.40, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] NETCD 136,50 TL takip seviyesi; 145 TL direnç olarak belirtilmiş."},
    "BURCE": {"entry_level": 35.0, "current_live_price": 35.70, "note": "[Oğuz Çelik][Borsa Eğitim/Analiz Kısa Vade][2026-08-14] BURCE 35 TL takip seviyesi. Görseldeki devam eden yorum kesik olduğu için ek hedef/stop uydurulmadı."},
}
for row in rows:
    update = updates.get(row.get("ticker"))
    if not update:
        continue
    old = {k: row.get(k) for k in ("entry_level", "support", "resistance", "current_live_price", "note")}
    row.setdefault("previous_records", []).append(old)
    row.update(update)
    row["captured_date"] = "2026-08-14"
path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Updated {len(updates)} Oğuz screenshot records")
