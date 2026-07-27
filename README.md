# Chartist Fibo-Scalp Pro

BIST 30 hisselerini son tamamlanmış resmî seans kapanışına göre puanlayan yerel karar destek panelidir.

## Çalıştırma

```powershell
pip install -r requirements.txt
python server.py
```

Ardından `http://127.0.0.1:8080` adresini açın. `index.html` dosyasını doğrudan açmak veri API'sini çalıştırmaz.

## Veri politikası

- Güncel fiyat, OHLC, hacim ve BIST 30 üyeliği: Borsa İstanbul resmî günlük bülteni
- BIST 100 kapanışı: Borsa İstanbul'un 15 dakika gecikmeli veri servisi
- Bir yıllık gösterge tarihçesi: Yahoo Finance
- Finansal/KAP verisi: henüz bağlı değil; pozisyon puanına etkisi `%0`
- Resmî kapanış bülteni bulunamazsa model güvenli moda geçer ve pozisyon önermez

Ekrandaki fiyatlar gerçek zamanlı değildir. Son tamamlanmış seansın resmî kapanış değerleridir.

## Pozisyon Puanı

- Teknik güç: `%78`
- Giriş zamanlaması: `%14`
- Stop güvenliği: `%8`
- Finansal kalite: `%0` — doğrulanmış KAP entegrasyonu gelene kadar devre dışı

`GİRİŞ UYGUN` kararı için puanın yanında trend, ADX, yön, göreli güç, risk ve giriş bölgesi eşikleri de birlikte sağlanmalıdır. `BEKLE` ve `AÇMA` durumlarında sanal pozisyon planlama düğmesi kilitlenir.

## Çalışan özellikler

- Resmî bültenden dinamik BIST 30 evreni
- Resmî kapanışla doğrulanan fiyat/OHLC/hacim
- Açıklanabilir teknik puan ve koşullu giriş kararı
- Arama, filtreleme ve sütun sıralama
- Dinamik strateji sayıları ve BIST 30 sektör ısı haritası
- CSV dışa aktarım
- Yalnız uygun adaylar için yerel sanal portföy
- Veri alınamazsa sahte fiyat göstermeyen güvenli hata durumu

> Bu uygulama yatırım tavsiyesi değildir. Backtest başarı oranı doğrulanmadığı için ekranda başarı yüzdesi gösterilmez.
