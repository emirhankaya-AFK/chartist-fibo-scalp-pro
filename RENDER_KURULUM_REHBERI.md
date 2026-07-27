# Render.com Ücretsiz/Bulut 7/24 Kurulum Rehberi 🚀

Bu kılavuz, **Chartist Fibo-Scalp Pro** projesini Render.com üzerinde 7/24 canlıya almak, 10K Robot Portföy verilerinin silinmesini önlemek ve Telegram / Telefona bildirim altyapısını kurmak için hazırlanmıştır.

---

## 1. Projeyi GitHub'a Yükleme

1. Bilgisayarınızda PowerShell açın ve proje klasörüne gidin:
   ```powershell
   cd C:\Users\emirh\Desktop\Kodlar\chartist-fibo-scalp-pro
   ```
2. Git deposu başlatın ve tüm dosyaları ekleyin:
   ```powershell
   git init
   git add .
   git commit -m "Render deployment ready - Chartist Fibo Scalp Pro"
   ```
3. [GitHub.com](https://github.com)'a girip yeni bir **Public** veya **Private** repo açın (Örn: `chartist-fibo-scalp-pro`).
4. GitHub'ın verdiği komutları çalıştırarak kodunuzu yükleyin:
   ```powershell
   git branch -M main
   git remote add origin https://github.com/KULLANICI_ADI/chartist-fibo-scalp-pro.git
   git push -u origin main
   ```

---

## 2. Render.com Kurulumu (1-Tıkla Otomatik Blueprint)

1. [Render.com](https://dashboard.render.com)'a gidin ve GitHub hesabınızla giriş yapın.
2. Sağ üstteki **New +** butonuna basıp **Blueprint** seçeneğine tıklayın.
3. GitHub reponuzu (`chartist-fibo-scalp-pro`) seçin ve **Connect**'e basın.
4. Render, proje içerisindeki `render.yaml` dosyasını otomatik algılayacaktır. 
   - Projeniz için `gunicorn` sunucusu ve **1 GB Kalıcı Disk (Persistent Disk)** otomatik oluşturulacaktır (Bu sayede 10K Robot portföy verileri sunucu kapansa bile silinmez!).
5. **Apply** butonuna tıklayın. Render projenizi 2-3 dakika içinde kuracak ve size canlı web adresinizi sunacaktır (Örn: `https://chartist-fibo-scalp-pro.onrender.com`).

---

## 3. Telegram ve NTFY Bildirim Ayarları (Opsiyonel)

Render Dashboard paneline girip projenizin **Environment** sekmesinden şu ortam değişkenlerini ekleyebilirsiniz:

### 📱 Telegram Bot Bildirimi İçin:
1. Telegram'da `@BotFather` ile görüşüp yeni bir bot açın ve **Bot Token** alın (Örn: `712345678:AAEb...`).
2. Telegram'da `@userinfobot` botuna tıklarak kendi **Chat ID** numaranızı öğrenin (Örn: `123456789`).
3. Render Dashboard -> **Environment Variables** bölümüne ekleyin:
   - `TELEGRAM_BOT_TOKEN`: `712345678:AAEb...`
   - `TELEGRAM_CHAT_ID`: `123456789`

### 📲 Telefona Anlık Push Bildirimi (NTFY):
- Telefona iOS/Android store'dan ücretsiz **ntfy** uygulamasını indirin.
- `emirkan_bist_alarm` başlığına abone olun.
- Render Dashboard -> **Environment Variables** bölümünde:
  - `NTFY_TOPIC`: `emirkan_bist_alarm`

---

## 4. Kullanım ve Canlı Bağlantı

Artık tarayıcınızdan Render'ın size verdiği canlı link üzerinden 7/24 sisteme erişebilir, robot portföyünüzü ve sinyalleri kesintisiz takip edebilirsiniz! 🚀
