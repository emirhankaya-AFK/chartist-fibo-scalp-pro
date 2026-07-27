# Chartist Fibo-Scalp Pro — Yeni AI Devir Dosyası

Bu dosya, projenin başka bir yapay zekâya devredilmesi için hazırlanmıştır. Kullanıcı: **Emirkan Kaya**. Proje adı kullanıcı konuşmalarında bazen “Mahmut”, “Chartist”, “Fibo-Scalp Pro” veya “Borsa Mobil Alarm” olarak geçmiştir. “Mahmut” ayrı bir kişi değil, proje/devir dokümanlarında kullanılan çalışma adıdır.

## 1. Kullanıcının asıl hedefi

Kullanıcı, Borsa İstanbul BIST100 hisselerini tarayan, teknik stratejilerle 0–100 puan veren, seçili hissede giriş/TP1/TP2/TP3/stop seviyelerini gösteren ve geçmiş performansı backtest ile ölçen bir karar destek sistemi istemektedir.

Sistem otomatik emir vermemeli; yalnızca karar desteği ve sanal portföy sağlamalıdır. Kullanıcı parasını riske atabileceğini söylediği için veri kaynağı, tarih, gecikme ve hesaplama yöntemi mutlaka açık yazılmalıdır. Kesin getiri veya yatırım garantisi verilmemelidir.

Kullanıcının kabul ettiği veri politikası: canlı veri mümkün değilse **15 dakika gecikmeli fiyat** gösterilebilir. Model sinyali için resmî BIST günlük kapanış doğrulaması ayrı tutulmalıdır. Ekrandaki “günlük değişim” ile ekrandaki güncel/15 dk gecikmeli fiyat aynı referansa göre hesaplanmalıdır.

## 2. Proje konumu

Ana proje:

`C:\Users\emirh\Desktop\Kodlar\chartist-fibo-scalp-pro`

Yerel adres:

`http://127.0.0.1:8080/`

Kullanıcı özellikle istemiştir: Çalışma sırasında Brave kendiliğinden açılmayacak. İş tamamlanınca yalnızca localhost adresi metin olarak verilecek; kullanıcı kendisi kopyalayıp açacak.

## 3. Dosya haritası

### Backend ve veri

- `market_scanner.py`: BIST100 evrenini, resmî BIST günlük bültenini, Yahoo Finance tarihçe ve 15 dk gecikmeli fiyatlarını okur. Teknik göstergeleri, 9 stratejiyi, model skorunu, hedef/stop seviyelerini ve veri kalitesi alanlarını üretir.
- `server.py`: Flask yerel API sunucusu. Port 8080.
- `backtest.py`: 2020’den bugüne walk-forward günlük backtest; taktik bazında işlem, pozitif oran, TP/stop oranı, ortalama getiri, drawdown vb. üretir.
- `batch_backtest.py`: Birden fazla ticker için backtest yardımcı scripti.
- `risk_engine.py`: Risk ve pozisyon büyüklüğü yardımcı hesapları.
- `analyst_benchmark.py`: Excel/analist alarm seviyelerini Chartist sinyalinden ayrı gösteren modül.
- `intraday_opportunity_worker.py`: Gün içi fırsat ve TP/stop yaşam döngüsü takipçisi. Kullanıcının son talebi üzerine otonom worker şu anda kapalı başlatılmaktadır (`ENABLE_OPPORTUNITY_WORKER=0`).

### Frontend

- `index.html`: Dashboard yapısı, sinyal tablosu, seçili hisse detayı, grafik, hedef/risk planı, Excel analist notları, bildirim merkezi ve modal ekranları.
- `app.js`: API çağrıları, filtreler, tablo sıralama, grafik dönemleri, seçili hisse, hedef planı modalı, backtest görünümü ve bildirim merkezi.
- `styles.css`: Koyu cam/terminal teması, yoğun tablo, responsive mobil düzen, hedef plan modalı, hızlı strateji şeridi ve bildirim kartları.

### Veri ve kayıt dosyaları

- `data\last_successful_scan.json`: Son başarılı BIST taramasının kalıcı cache kopyası. Soğuk açılışta ekranın uzun ağ taraması beklemeden açılmasını sağlar.
- `notification_log.json`: Bildirim/işlem olayı geçmişi.
- `tracking_log.json`: Manuel veya model bazlı takip fiyat gözlemleri.
- `server.out.log`, `server.err.log`, `server.stdout.log`, `server.stderr.log`: Yerel sunucu logları.
- `requirements.txt`: Python bağımlılıkları.

Excel notları için varsayılan yol:

`C:\Users\emirh\Desktop\Hisselerin_Teknik_Verileri.xlsx`

Bu dosya yoksa sistem Excel notlarını boş gösterebilir; bu durum model skorunu bozmaz, fakat analist seviyeleri görünmez.

## 4. API uçları

- `GET /api/health`: Sunucu, worker, güvenlik ve emir yürütme durumunu döndürür.
- `GET /api/scan`: Cache-first piyasa verisi. Normal ekran açılışı bunu kullanmalıdır.
- `GET /api/scan/refresh`: Zorla tam ağ taraması. Kullanıcı açıkça yenile demedikçe frontend bunu çağırmamalıdır; BIST100 geçmişi ve 15 dk verisi nedeniyle uzun sürebilir.
- `GET /api/backtest/<TICKER>`: 2020’den bugüne ticker backtesti.
- `GET /api/analyst-notes`: Excel seviyelerini döndürür.
- `GET /api/analyst-alerts`: Oğuz, Ahmet Mergen ve diğer analist alarm geçmişi.
- `GET /api/notifications`: İşlem olayları, telefon bildirim geçmişi ve takip durumu.
- `POST /api/tracking/manual`: Manuel ticker takibi başlatır.

## 5. Veri kaynakları ve önemli doğruluk kuralları

### Borsa İstanbul

Resmî günlük bülten, sinyal tarihinin kapanış doğrulaması için ana kaynaktır. Modelin tarihsel teknik hesabı ve resmî OHLC alanları bu doğrulama katmanına dayanır.

### Yahoo Finance

Yahoo Finance iki amaçla kullanılır:

1. Teknik indikatörler için tarihçe.
2. Ekranda gösterilen 15 dakika gecikmeli fiyat ve gün içi grafik.

Ekranda gösterilen hisse `price` alanı, gecikmeli fiyat geldiğinde 15 dk gecikmeli fiyat olarak değiştirilir. Orijinal model sinyal fiyatı `signalPrice` alanında tutulur. `priceSource` ve `priceTimestamp` mutlaka gösterilmelidir.

### Google Finance

Google Finance, backend için doğrudan güvenilir bir API değildir. Google’ın kendi belgelerine göre `GOOGLEFINANCE` esas olarak Google Sheets fonksiyonudur; gecikme olabilir, geçmiş veri Sheets API/Apps Script ile indirilemez ve birçok uluslararası borsa desteklenmez. Bu nedenle ana BIST100 kaynağı yapılmamalıdır. İleride yalnızca karşılaştırma/yedek gösterge olarak kullanılabilir.

### Günlük yüzde hesabı

Günlük yüzde, ekrandaki güncel gecikmeli fiyat ile `officialOhlc.previousClose` karşılaştırılarak hesaplanır. Resmî kapanışın eski yüzde değişimi doğrudan ekrana basılmamalıdır; aksi halde kullanıcı güncel fiyat ile yüzdeyi çelişkili görür.

## 6. Model ağırlıkları

Mevcut model yaklaşık olarak:

- Teknik kalite: %78
- Giriş zamanlaması: %14
- Stop güvenliği: %8
- Finansal doğrulama: doğrulanmış veri yoksa puana katılmaz

Model skoru 0–100 arasıdır. Model skoru kesin getiri anlamına gelmez. `modelAnalysis.confidence` model güvenini, `strategyQuality` seçili algoritmanın kalite puanını ifade eder.

## 7. Mevcut 9 strateji

1. **Dipten Dönüş:** SMI/RSI/CCI dip ve yukarı kesişim onayı.
2. **Derin Dönüş:** Derin aşırı satım, hacim ve osilatör dönüşü.
3. **Uzun Vade:** Fiyatın ana ortalamalar ve yükselen yapı üzerinde olması.
4. **Momentum Kırılımı:** Hacim, momentum ve direnç kırılımı.
5. **CRSI Scalp:** Connors RSI ve kısa vadeli aşırı sarkma tepkisi.
6. **Chartist MM Trend:** Trend, ADX ve yapı uyumu.
7. **Wyckoff Spring:** Destek altı likidite süpürmesi ve destek üstü dönüş.
8. **Money Dip:** MFI/hacim vekili. Gerçek takas verisi değildir; UI bunu açıkça yazmalıdır.
9. **Chartist Trender:** Trend içi düzeltme/pullback sonrası devam.

Bir hisse birden fazla stratejiyi karşılayabilir. `strategyMatches` tüm eşleşmeleri, `strategy` birincil stratejiyi, `strategyEvidence` kanıtları taşır.

## 8. OBO / TOBO durumu

OBO (Omuz-Baş-Omuz) ve TOBO (Ters Omuz-Baş-Omuz) şu anda gerçek bir algoritma olarak mevcut değildir. Kodda bu formasyon için boyun çizgisi, omuz-baş oranı, kırılım, hacim, hedef ve stop hesaplayan fonksiyon bulunmamaktadır.

Yeni AI bu özelliği eklerse yalnızca “etiket” eklememeli; şu alanları üretmelidir:

- `pattern`: `OBO`, `TOBO` veya `null`
- `patternConfidence`
- `neckline`
- `leftShoulder`, `head`, `rightShoulder`
- `breakoutConfirmed`
- `patternTarget`
- `patternStop`
- Formasyonun hangi tarih aralığında oluştuğu
- Backtest sonucu

Kırılım doğrulanmadan OBO/TOBO “al” sinyali verilmemelidir.

## 9. Grafik ve hedef/risk planı

Grafik dönemleri:

- `1G`: gün içi 15 dk gecikmeli grafik
- `1H`: yaklaşık son 5 seans
- `1A`: yaklaşık son 22 seans
- `3A`: yaklaşık son 66 seans

Grafikte dönem getirisi, başlangıç/son fiyat, TL farkı, düşük-yüksek aralığı gösterilir.

Seçili hisse detayında yıldızın yanında **Planı Aç** düğmesi vardır. Bu düğme hisseyi ortalayan büyük planda şunları gösterir:

- Güncel 15 dk gecikmeli fiyat
- Günlük değişim
- Giriş bölgesi
- Stop ve fiyata uzaklığı
- TP1/TP2/TP3 ve mevcut fiyattan beklenen yüzde
- R/R
- Model kararı
- Fiyat kaynağı ve timestamp

Otomatik emir yoktur.

## 10. Analist ve Excel mantığı

Kullanıcı özellikle Oğuz, Ahmet Mergen ve diğer analistlerin notlarının modelden ayrı ve anlaşılır görünmesini istemiştir. Excel’de “Hedef 10 TL”, “direnç”, “stop” gibi ham metinler kullanıcıya olduğu gibi bırakılmamalı; hisse seçildiğinde şu açıklanmalıdır:

- Nereden takip ediliyor?
- Hangi destek/direnç?
- Hangi fiyat koşulunda alım veya izleme?
- Hangi fiyat koşulunda satış/stop?
- Notun kaynağı ve tarihi
- Model sinyaliyle analist notu uyuşuyor mu?

Analist notu model sinyaliymiş gibi gösterilmemelidir.

## 11. Bildirim sistemi

Bildirim merkezinde şu olay türleri tasarlanmıştır:

- TP1 görüldü
- TP2 görüldü
- TP3 görüldü
- Kârlı/trailing stop tetiklendi
- Normal stop tetiklendi

Kartlarda giriş, hedef, gerçekleşen fiyat, gerçekleşen getiri, sinyal zamanı, gerçekleşme zamanı, geçen süre, görülen maksimum fiyat/kâr ve algoritma bulunmalıdır. Aynı ticker ve aynı olay türü tekrar tekrar kaydedilmemelidir.

`NTFY_TOPIC` tanımlı değilse telefona gerçek bildirim gönderilemez. UI bunu saklamamalı; ancak ham “başarısız deneme” çöplüğü de göstermemelidir. Telefon geçmişinde yalnızca gerçekten gönderilen veya yerel işlem olayı olarak kaydedilen kayıtlar görünmelidir.

Kullanıcının son kararı doğrultusunda otonom worker kapalı çalıştırılmaktadır. Telefon bildirimi ve TP yaşam döngüsü izleme istenirse worker kontrollü şekilde yeniden açılmalı ve önce sanal veriyle test edilmelidir.

## 12. Performans kararları

Yapılmış hız iyileştirmeleri:

- Cache-first `GET /api/scan`.
- `data\last_successful_scan.json` ile soğuk açılışta kalıcı cache.
- Frontend otomatik yenilemesi force refresh yerine normal cache endpointine çekildi.
- Otonom worker kapatıldı.
- Yahoo çoklu ticker indirmesinde `threads=True` kullanılıyor.

Yavaş olan işlem `GET /api/scan/refresh`’tir; bu çağrı resmî bülten, 1 yıllık 99 ticker tarihçesi ve 15 dk gün içi verisini yeniden indirir. Bunu sayfa açılışında veya her birkaç dakikada bir çalıştırma.

GPU kullanımı şu an eklenmemiştir. Pandas/NumPy tabanlı bu yükte GPU zorunlu değildir; önce ağ ve cache darboğazı çözülmelidir. GPU eklenecekse CUDA/numba/cupy varlığı tespit edilmeli ve yalnızca benchmark sonucu CPU’dan hızlıysa kullanılmalıdır. Sabit “GPU’nun yüzde 10–20’sini kullan” garantisi verilmemelidir.

## 13. Referans ekran görüntüleri

Kullanıcının referans klasörü:

`C:\Users\emirh\Downloads\New folder`

Bu klasörde kod veya Excel değil, yaklaşık 50 adet PNG/JFIF ekran görüntüsü vardır. Görsel ortak özellikler:

- Koyu lacivert yoğun tablo
- Çok sütunlu strateji, teknik, trend, sentiment, para akışı, master puan, geliş, periyot, pozisyon, giriş, güncel, günlük yüzde, TP1/TP2/TP3 ve stop görünümü
- Renkli strateji filtre çipleri ve adetleri
- TP1/TP2 hedef kartlarında giriş, hedef, sinyal tarihi, gerçekleşme tarihi, geçen süre ve gerçekleşen kâr
- Kârlı stop kartı
- Responsive mobil hedef kartları

Projeye bu referanslardan hızlı strateji şeridi, hedef/risk modalı ve işlem olay kartları uyarlanmıştır. Görseller birebir kopyalanmamalı; veri ve marka isimleri sahte kullanılmamalıdır.

## 14. Bilinen eksikler

- OBO/TOBO henüz hesaplanmıyor.
- ntfy ortam değişkenleri yoksa gerçek telefon push bildirimi yoktur.
- Finansal/KAP puanı doğrulanmış bir veri bağlantısı olmadan modele dahil değildir.
- Money Dip gerçek takas verisi değil, MFI/hacim vekilidir.
- 15 dk gecikmeli fiyat Yahoo kaynağının güncellemesine bağlıdır.
- Resmî BIST günlük veri ve gecikmeli gün içi fiyat farklı timestamp taşıyabilir; UI her ikisini açıkça ayırmalıdır.
- Backtest strateji bazındadır; mevcut pozisyon skorunun geçmişte birebir aynı sonucu verdiği anlamına gelmez.
- Sistemde otomatik emir gönderimi yoktur.

## 15. Yeni AI için ilk kontrol listesi

1. `python -m py_compile market_scanner.py server.py backtest.py intraday_opportunity_worker.py`
2. `node --check app.js`
3. `GET /api/health` sonucu `status=ok` olmalı.
4. `GET /api/scan` 5 saniyeden kısa sürede cache’den cevap vermeli.
5. `stocks` yaklaşık 99 hisse içermeli; dışlanan ticker’lar `errors` alanında yazmalı.
6. Her stock için `price`, `signalPrice`, `priceSource`, `priceTimestamp`, `daily` tutarlı olmalı.
7. `daily`, ekrandaki gecikmeli fiyat ile previous close üzerinden hesaplanmalı.
8. OBO/TOBO etiketi yoksa bunu varmış gibi gösterme.
9. Worker kapalıysa bunu UI’da açıkça yaz; telefon bildirimi gönderilmiş gibi davranma.
10. Brave’i otomatik açma. Kullanıcıya yalnızca localhost adresi ver.

## 16. Çalıştırma

Proje klasöründe:

```powershell
cd C:\Users\emirh\Desktop\Kodlar\chartist-fibo-scalp-pro
python server.py
```

Otonom worker kapalı başlatmak için:

```powershell
$env:ENABLE_OPPORTUNITY_WORKER="0"
python server.py
```

Sonra kullanıcıya şu adres verilir:

`http://127.0.0.1:8080/`

## 17. Kullanıcı iletişim kuralları

- Türkçe, kısa ve doğrudan yaz.
- Kullanıcı istemeden Brave açma.
- Kullanıcı “hızlı” dediğinde uzun ağ taraması çalıştırma.
- Bir şey mevcut değilse açıkça “yok” de; sahte veri gösterme.
- Veri kaynağı, gecikme ve timestamp’i saklama.
- Para yatırılacak sistem olduğu için test edilmemiş formasyonu gerçek sinyal gibi sunma.
- Kod silme gibi yıkıcı işlemleri yedek almadan yapma.
