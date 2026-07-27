# Chartist Fibo-Scalp Pro ile Projemizin Karşılaştırması

Bu değerlendirme, paylaşılan kullanım kılavuzu ve iki dashboard ekranındaki görülebilen özelliklere dayanır. Rakip uygulamanın kaynak kodu, gerçek veri doğruluğu ve geçmiş performansı elimizde olmadığı için bunlar doğrulanmış kabul edilmemiştir.

## Kısa sonuç

Rakip sistem şu anda **veri ve analiz motoru bakımından önde**, bizim proje ise güncel tasarımıyla **kararın açıklanması ve en iyi pozisyonun doğrudan gösterilmesi bakımından daha güçlü**.

Bizim arayüzün gerçek ürüne dönüşmesi için eksik olan ana parça tasarım değil; canlı BIST verisi, finansal tablo verisi, indikatör hesaplama motoru ve doğrulanmış backtest altyapısıdır.

## Yan yana karşılaştırma

| Alan | Rakip sistem | Bizim proje | Durum |
|---|---|---|---|
| Sinyal evreni | Ekranda 200'den fazla sinyal satırı görülüyor | Güncel BIST 30 taraması | Rakip önde |
| Canlı veri | Kılavuz ve ekran canlı veri kullandığını belirtiyor | Gecikmeli/gün sonu gerçek piyasa verisi | Rakip önde |
| Strateji motoru | Yedi teknik strateji belgelenmiş | Stratejiler arayüzde modellenmiş, hesaplama backend'i yok | Rakip önde |
| Temel analiz | Güncel bilanço, Guru, Altman ve Piotroski iddiası var | Erişilebilen gerçek finansal rasyolar var; KAP ve Piotroski henüz yok | Rakip önde |
| SMC tespiti | Likidite, FVG, MSS, OB ve Emilim taraması tanımlanmış | Aynı onaylar veri modeline ve puana dahil | Motor kurulunca eşitlenebilir |
| Risk yönetimi | TP1-TP3, dinamik stop ve üç çıkış modeli var | TP1-TP3, stop, R/R ve sanal pozisyon planı var | Yakın |
| Ana sıralama | Master Puan ile tablo sıralaması | Master yanında bağımsız Pozisyon Puanı | Bizim yaklaşım daha seçici |
| En iyi pozisyon | Paylaşılan ekranda tek bir açık model lideri görünmüyor | Model Lideri ve ilk üç aday doğrudan gösteriliyor | Bizim proje önde |
| Açıklanabilirlik | Çok sayıda skor var; kesin Master ağırlıkları paylaşılmamış | Her pozisyonun teknik, finansal, SMC, R/R, giriş ve stop etkisi görünür | Bizim proje önde |
| Zamanlama kontrolü | Güncel fiyat, hedef ve stop gösteriliyor | Fiyat girişten uzaklaştığında puan düşüyor ve “kovalama” uyarısı çıkıyor | Bizim proje önde |
| Kullanılabilirlik | Çok yoğun, profesyonel terminal görünümü | Daha okunabilir özet ve detay hiyerarşisi | Kullanıcı tipine bağlı |
| Geçmiş doğrulama | Paylaşılan içerikte kanıtlanmış sonuç raporu yok | Henüz backtest yok | İkisinde de doğrulama gerekli |

## Bizim Pozisyon Puanımızın farkı

Rakip sistemin Master Puanı şirket ve sinyal kalitesini birleştiriyor. Bizim Pozisyon Puanı buna ek olarak **o anda pozisyona girmenin ne kadar uygun olduğunu** ölçüyor.

Formül:

```text
Pozisyon Puanı =
  Teknik Güç × 0.68
  + Finansal Kalite × 0.17
  + Giriş Tazeliği × 0.10
  + Stop Güvenliği × 0.05
```

Teknik güç; trend, momentum, ADX/DMI, hacim, BIST 100 göreli güç ve fiyat yapısından oluşur. Ham puanın yanında giriş için ADX, +DI/-DI, stop mesafesi, göreli güç ve fiyatın giriş bölgesinde olması gibi sert geçiş kuralları uygulanır.

Bu ayrım önemlidir:

- İyi şirket, her fiyattan iyi pozisyon değildir.
- Güçlü sinyal, hedefe çok yaklaştıysa geç kalınmış olabilir.
- Çok yüksek R/R, stop aşırı yakın olduğu için yanıltıcı olabilir.
- Aktif SMC onaylarının birlikte görülmesi tek bir onaydan daha değerlidir.

## 16 Temmuz 2026 kapanış taraması

Modelin sert giriş kurallarını geçen adaylar:

1. `TRALT` — 81,2
2. `THYAO` — 74,3

`ASTOR` ham puanda 81,6 olmasına rağmen ADX ve stop mesafesi giriş kuralını geçemediği için izleme listesinde kaldı. Bu ayrım, ham puanı yüksek her hissenin otomatik olarak pozisyon adayı yapılmadığını gösterir.

Bu çıktı gecikmeli/gün sonu verisine dayanır ve gelecek getiriyi garanti etmez.

## Rakibi gerçekten geçmek için gerekenler

1. BIST fiyat, hacim ve endeks verisini güvenilir bir sağlayıcıdan almak.
2. Yedi stratejiyi Python tarama motorunda birebir ve test edilebilir kurallarla hesaplamak.
3. KAP finansallarıyla Altman, Piotroski ve Guru skorlarını otomatik üretmek.
4. Her sinyal için kullanılan veri zamanı, kural sonucu ve puan katkısını kaydetmek.
5. En az üç-beş yıllık, komisyon ve kayma içeren walk-forward backtest yapmak.
6. Başarıyı yalnızca kazanma oranıyla değil; maksimum düşüş, expectancy, profit factor ve Sharpe ile ölçmek.
7. Gerçek para öncesinde sanal portföyde sinyalleri değiştirilemez zaman damgasıyla izlemek.

Bu aşamalar tamamlanmadan iki ürün arasında yalnızca arayüz ve özellik listesi karşılaştırması yapılabilir; gerçek üstünlük performans verisiyle kanıtlanmalıdır.
