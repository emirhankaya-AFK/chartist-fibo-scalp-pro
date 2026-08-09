# 🇺🇸 ABD Piyasaları (NASDAQ / NYSE) Small-Cap Short Satış & Squeeze Önleme Stratejisi

> **Not:** Bu doküman, gelecekte ABD (US Small-Cap / OTC) piyasaları için geliştireceğimiz özel Short Taramaları, Squeeze Koruması ve Sulandırma (Dilution) Takip Sistemi için hazırlanmış strateji mimarisi ve yol haritasıdır (David Capablanca / TraderLion Playbook Esaslıdır).

---

## 📌 1. Temel Felsefe: Kötü Şirket vs. Mükemmel Short İşlemi

1. **"Kötü Şirket" Tek Başına Short Sebebi Değildir:**
   - Nakit sıkıntısı çeken, sürekli hisse basarak sulandıran veya bilançosu berbat şirketler en tehlikeli parabolik squeeze (%1.000 – %10.000 yükseliş) hareketlerini yapabilir.
   - Şirket tezinde sonuna kadar haklı olsanız bile zamanlama (timing) yanlışsa hesap sıfırlanabilir.

2. **Arka Yüz (Backside) ve Trend Kırılımı Teyidi:**
   - **Frontside (Ön Yüz):** Parabolik yükseliş aşaması. Trend 45 derece dik devam ederken önüne geçilmez.
   - **Backside (Arka Yüz):** Fiyatın düzenli trendi kırdığı, blow-off top (son alıcı temizliği) yaptığı ve İlk Kırmızı Gün (First Red Day) teyidinin alındığı aşama.

---

## 🔬 2. "Dubious Company" (Şüpheli Şirket) Profilleme Kriterleri

Gelecekte ABD tarama motorumuza dahil edilecek temel veriler:

* **Piyasa Değeri:** < 250 Milyon $ (Özellikle Nano/Micro-Cap evreni).
* **Nakit Ömrü (Cash Runway):** < 3–6 Ay (Özellikle 3 aydan az nakdi kalanlar acil finansman/sulandırma adayıdır).
* **Sulandırma Kriterleri:**
  - Registered Warrants (Kayıtlı warrantlar) & Kullanım Fiyatları (Inducement riskleri).
  - ATM (At-the-Market) & S-3 Shelf Kapasitesi.
  - Reverse Split (Hisse Birleştirme) Geçmişi.
* **Tema Manipülasyonu:** Şirketin sonradan moda temalara (Blockchain -> Savunma, EV Golf Kart -> Yapay Zekâ vb.) isim değiştirmesi.
* **Halka Açık Pay (Float):** < 1 Milyon pay (Nano-Float) hisseler aşırı squeeze riskli olup short'tan muaf tutulmalıdır.

---

## ⚠️ 3. İşlem Güvenliği ve Kırmızı Çizgiler (Risk Kuralları)

1. **Nano-Float & Çin Hisseleri Muafiyeti:**
   - Float < 1M olan hisselerde short açılmaz.
   - Çin merkezli hisseler T12 (SEC İşlem Durdurma) ve 10 aylık kilitlenme riski nedeniyle taranmaz.
2. **Locate / Borçlanma Maliyeti (Borrow Rate):**
   - Borçlanma oranı %50 – %900 üzerindeyse, doğru yönde işlem açılsa bile taşıma maliyeti kârı yutar.
3. **Biotech Gece Taşıma Riski:**
   - Biyotik hisseleri piyasa öncesi (Pre-market) haber ve gap riski nedeniyle geceye (Overnight) taşınmaz.

---

## 🛠️ 4. Gelecekteki Yazılım & Modül Planı

* **ABD Tarayıcı Entegrasyonu:** Trade Ideas / Thinkorswim API & SEC EDGAR Filings (S-3, 10-Q) otomasyonu.
* **First Red Day & Blow-Off Alarm Motoru:** Parabolik yükseliş sonrası ilk %5+ kırılımda anlık bildirim.
* **Short Squeeze Risk Puanlaması:** Float, Short Interest, Borrow Rate kombinasyon puanı.

---
*Gelecekte ABD piyasaları modülü aktif edileceği zaman bu strateji mimarisi temel alınacaktır.*
