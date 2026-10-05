# Railway hazırlığı

Bu servis yalnızca güvenli bekleme döngüsü ve `/health` endpoint'i açar.
YouTube işlemleri, OAuth, otomatik Shorts üretimi ve Google Drive aktarımı etkin değildir.
Mevcut Shorts betikleri değiştirilmemiştir; manuel komutlarla kullanılabilir.

## Kurulum

1. PR birleştirildikten sonra Railway'de bu depoyu seçin; kök dizin `/` olsun.
2. Kök Dockerfile Python 3.11, FFmpeg ve Python bağımlılıklarını kurar.
   Debian FFmpeg paketi libx264, AAC ve subtitles/libass desteğini sağlar;
   Docker build sırasında encoder/filter kontrolleri çalışır.
   DejaVu fontları Türkçe karakterleri destekler.
3. Başlangıç komutu: `python -u worker.py`.
4. Railway'in sağladığı `PORT` kullanılır (yerelde varsayılan 8080).
   Healthcheck yolu `/health`; başarılı yanıt HTTP 200 ve
   `{"status": "ok", "mode": "idle"}` olur.
5. Railway Variables bölümüne aşağıdaki OAuth değişkenlerini ekleyin:
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`
   Değerleri yalnızca Railway'de saklayın; depoya veya ekran görüntülerine eklemeyin.
   Servis açılışta salt okunur kanal doğrulaması yapar. Değişkenlerden biri eksik veya geçersizse güvenli şekilde başlatılmaz. 

## Yerel kontrol

```bash
docker build -t youtube-worker .
docker run --rm -p 8080:8080 -e PORT=8080 youtube-worker
curl http://localhost:8080/health
```

SIGTERM/SIGINT bekleme döngüsünü durdurur ve HTTP sunucusunu kapatır.
Whisper modeli başlangıçta indirilmez. Gelecekte transkripsiyon etkinleştirilirse
model indirme erişimi, bellek kapasitesi ve kalıcı dosya depolaması ayrıca hazırlanmalıdır.
Bu PR deploy veya otomatik yayın başlatmaz.
