# Demo Trading Botu Yeniden Kurulum Planı

## Hedef

Render üzerinde çalışan, 3.500 USD sanal bakiyeli, BIST/ABD/kripto piyasalarını izleyen ve yalnızca kullanıcı komutuyla demo işlem açan cloud-first sistem.

## Bütçe sınırları

- BIST: 1.000 USD
- ABD: 1.000 USD
- Kripto spot izleme: 1.000 USD
- Kripto kaldıraç teminatı: 500 USD
- Gerçek emir: kapalı

## Aşamalar

### Aşama 1 — Temel ve güvenlik

- Tek Python web servisi korunacak.
- SQLite ile portföy, emir, pozisyon, açıklama ve token kayıtları tutulacak.
- NVIDIA anahtarları yalnızca ortam değişkenlerinden okunacak.
- API anahtarı, log ve kullanıcı sırrı cevaplarda gösterilmeyecek.
- Sağlık, hata ve yapılandırma endpoint’leri eklenecek.

### Aşama 2 — Demo işlem motoru

- Kullanıcı komutundan sembol, piyasa, yön, teminat ve kaldıraç ayrıştırılacak.
- TP1, TP2, stop ve manuel kapatma desteklenecek.
- Kripto kaldıraç üst sınırı ve teminat limiti uygulanacak.
- Her işlem için giriş, çıkış, PnL, risk, zaman ve gerekçe kaydedilecek.

### Aşama 3 — Çalışanlar

- Super hızlı özet ve ikinci görüş üretecek.
- Ultra risk, senaryo ve işlem gerekçesi üretecek.
- Çalışan yanıtı işlem açma yetkisine sahip olmayacak; yalnızca analiz sağlayacak.
- Token kullanımı ve yanıtlar SQLite’a yazılacak.

### Aşama 4 — Piyasa veri adaptörleri

- BIST veri kaynağı mevcut güvenli mod ile korunacak.
- ABD ve kripto için veri sağlayıcı adaptörleri ayrı modüller olacak.
- Veri tazeliği, kaynak ve gecikme her yanıtta gösterilecek.

### Aşama 5 — Arayüz ve bulut

- Portföy, açık pozisyonlar, emir geçmişi, çalışan açıklaması ve token kullanımı gösterilecek.
- Render env değişkenleri ve health check tamamlanacak.
- CI/test olmadan canlı deploy yapılmayacak.

## Kabul kriterleri

- Demo bakiye toplamı 3.500 USD’den sapmıyor.
- Kripto teminatı 500 USD’yi aşamıyor.
- TP1/TP2/stop/manual close kayıtları tekrar üretmiyor.
- Her işlemde çalışan gerekçesi veya açık hata kaydı var.
- API anahtarları hiçbir response, log veya Excel çıktısında görünmüyor.
- Gerçek broker/emir endpoint’i yok veya devre dışı.
