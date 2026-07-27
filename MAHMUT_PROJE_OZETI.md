# Mahmut — Chartist Fibo-Scalp Pro Proje Özeti

Bu dosya, projeyi başka bir yapay zekâya devretmek için hazırlanmıştır.

## Proje konumu

`C:\Users\emirh\Desktop\Kodlar\chartist-fibo-scalp-pro`

Localhost:

`http://127.0.0.1:8080`

## Amaç

BIST100 hisselerini tarayan, teknik sinyal ve risk planı üreten, Excel’den gelen manuel analist seviyelerini ayrı gösteren, 2020’den bugüne taktik backtesti yapabilen karar destek sistemi.

Otomatik gerçek para emri göndermez. Sanal portföy ve araştırma amaçlıdır.

## Dosyalar

- `index.html`: Ana arayüz ve tablo düzeni.
- `styles.css`: Koyu tema, tablo, grafik, kartlar, badge’ler ve responsive tasarım.
- `app.js`: Filtreler, sıralama, grafik, detay paneli, backtest çağrısı, Excel notlarının görünümü ve sanal portföy arayüzü.
- `market_scanner.py`: Resmî Borsa İstanbul bülteni, Yahoo tarihçesi, teknik puanlama, BIST100 taraması ve gecikmeli makro fiyatlar.
- `backtest.py`: 2020’den bugüne günlük walk-forward backtest motoru.
- `batch_backtest.py`: BIST30/BIST100 evreninde toplu backtest.
- `server.py`: Flask localhost sunucusu ve API endpoint’leri.
- `requirements.txt`: Flask, NumPy, Pandas ve yfinance bağımlılıkları.
- `RAKIP_KIYASLAMASI.md`: Rakip ekran ve model kıyaslaması.
- `README.md`: Kısa kullanım ve veri politikası.
- `MAHMUT_PROJE_OZETI.md`: Bu devir dokümanı.

## Çalıştırma

PowerShell:

```powershell
cd C:\Users\emirh\Desktop\Kodlar\chartist-fibo-scalp-pro
python server.py
```

Sonra `http://127.0.0.1:8080` adresini aç.

## API

- `GET /api/scan`: Güncel BIST100 taraması.
- `GET /api/scan/refresh`: Önbelleği zorlayarak yeni tarama.
- `GET /api/backtest/<TICKER>`: Tek hisse için 2020’den bugüne taktik backtesti.
- `GET /api/health`: Sunucu ve veri politikasını kontrol eder.

## Veri politikası

- Sinyal fiyatı: Borsa İstanbul resmî günlük bülteni.
- Teknik tarihçe: Yahoo Finance günlük tarihçesi.
- 15 dakikalık gösterim fiyatı: Yahoo Finance intraday; sinyal puanını değiştirmez ve doğrulanmış kabul edilmez.
- BIST100 resmi evreninden şu an 100 hisse bulunur; tarihçe yetersizliği nedeniyle teknik tarama bir hisse eksik kalabilir.
- Finansal/KAP ve takas/para akışı puanı henüz modele dahil değildir.

## Puanlama

Model puanı 0–100 ölçeğindedir.

- Teknik kalite: %78
- Giriş zamanlaması: %14
- Stop/risk güvenliği: %8
- Finansal/KAP: %0 (doğrulanmış veri bağlantısı bekleniyor)

Teknik bileşenler:

- EMA trend hizası
- RSI ve MACD momentum
- ADX ve DI yönü
- Hacim oranı
- BIST100’e göre göreli güç
- Yapı/kırılım
- Giriş bölgesi
- ATR ve yapısal stop
- FVG, MSS, LIQ, OB, EMA5-8-13 ve VCP bayrakları

Güvenlik düzeltmesi: ADX veya hacim teyidi yoksa trend puanı artık 100’e çıkamaz.

## Excel entegrasyonu

Kaynak dosya:

`C:\Users\emirh\Desktop\Hisselerin_Teknik_Verileri.xlsx`

Okunan sayfalar:

- `BIST Takip Listesi`
- `Aktif Alarmlar (Premium)`

Gösterilen alanlar:

- Giriş maliyeti
- Destek seviyesi
- Direnç seviyesi
- Kâr hedefi
- Oğuz analiz notu
- Alarm hedefi ve alarm açıklaması

Excel notları model puanını otomatik olarak değiştirmez; detay panelinde ve tabloda ayrı kaynak olarak gösterilir. Örnek: `EREGL — Trend bozulmadıkça stop seviyesi — Alarm seviyesi: 36 TL`.

## Backtest

`market_scanner.py` ve `backtest.py` içindeki dokuz bağımsız algoritma:

- Dipten Dönüş — SMI kesişimi, RSI ve CCI
- Derin Dönüş — 60 günlük düşüş, SMI/Stokastik dönüş ve hacim
- Uzun Vade — EMA20/EMA50/SMA200 trend dizilimi ve ADX
- Momentum Kırılımı — 20 günlük direnç, hacim ve MACD
- CRSI Scalp — Connors RSI ile kısa vadeli aşırı sarkma
- Chartist MM Trend — güçlü trend, ADX ve VCP vekili
- Wyckoff Spring — destek altı likidite süpürmesi ve geri alım
- Money Dip — MFI/hacim vekili ile fiyat/para akışı ayrışması
- Chartist Trender — yükselen trendde EMA20 çevresi pullback dönüşü

Bir hisse birden fazla algoritmaya uyabilir. En yüksek algoritma kalite puanı ana strateji etiketi olur; diğer eşleşmeler detay panelinde tutulur. Money Dip gerçek aracı kurum takas verisi kullanmaz; mevcut veri kaynağında bulunmadığı için MFI ve hacim açıkça vekil olarak kullanılır.

Varsayımlar:

- Başlangıç: 2020-01-01
- Günlük veri
- Komisyon: %0,10
- Kayma: %0,05
- Stop: 1,5 ATR
- Hedef: 2 ATR
- Aynı anda üst üste pozisyon açılmaz.

Backtest sonuçları geçmiş performanstır; gelecek garantisi değildir. Güncel BIST üyelerini geçmişe uygulamak survivorship bias oluşturabilir.

## Filtreler

- BIST100 evreni
- Adaylar: `OPEN / GİRİŞ UYGUN`
- İzlenenler: `WATCH / BEKLE`
- Strateji filtresi
- Minimum pozisyon puanı
- SMC badge filtresi
- Hisse arama
- Teknik/pozisyon puanı sıralaması

## Bilinen eksikler

1. Tarihçe yetersiz olan bir BIST100 hissesi tarama dışında kalabilir.
2. Sanal portföyden pozisyon silme/düzenleme arayüzü tamamlanmalıdır.
3. Grafik dönem butonları gerçek ayrı tarihçe çekimlerine bağlanmalıdır.
4. Toplu BIST100 backtest özeti dashboard’a bağlanmalıdır.
5. Geçmiş BIST üyelik değişimleri backtestte kullanılmalıdır.
6. Finansal/KAP ve takas/para akışı veri sağlayıcıları bağlanmalıdır.
7. Gerçek emir entegrasyonu bilinçli olarak kapalıdır.

## Devralacak yapay zekâ için önemli not

Önce `README.md` ve bu dosyayı oku. Sonra `server.py`, `market_scanner.py`, `backtest.py`, `app.js`, `index.html` sırasıyla incelenmeli. Her değişiklikten sonra:

```powershell
node --check app.js
python -m py_compile market_scanner.py backtest.py server.py batch_backtest.py
```

API kontrolü:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health
Invoke-RestMethod http://127.0.0.1:8080/api/scan
Invoke-RestMethod http://127.0.0.1:8080/api/backtest/EREGL
```

Gerçek para kullanımı öncesi sanal portföy, işlem günlüğü, maksimum düşüş ve veri tazeliği kontrolleri tamamlanmalıdır.
