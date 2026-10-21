# emotion-recognition-web

Deteksi emosi wajah **real-time** langsung dari browser, ditenagai DeepFace + Flask.

![stack](https://img.shields.io/badge/Python-3.10--3.13-blue) ![flask](https://img.shields.io/badge/Flask-3.1-black) ![tf](https://img.shields.io/badge/TensorFlow-2.21-orange)

## ✨ Fitur

- **Kamera di browser** (WebRTC `getUserMedia`) – bisa dipakai dari laptop/HP mana pun, bukan hanya kamera server. Pilih kamera, mode cermin, layar penuh.
- **Multi-wajah** dengan kotak, label, dan emoji animasi di atas setiap wajah.
- **Skor 7 emosi** (senang, sedih, marah, terkejut, netral, jijik, takut) + *smoothing* agar hasil stabil, plus **skor suasana hati** positif ↔ negatif.
- **Perkiraan usia & gender** (opsional).
- **Analisis foto**: unggah, seret & lepas, atau tempel (Ctrl+V) gambar.
- **Grafik live** (Chart.js): timeline emosi dan distribusi per sesi.
- **Riwayat tersimpan di SQLite**: filter per emosi, statistik, ekspor CSV, hapus.
- **Snapshot** PNG lengkap dengan overlay.
- **Pengumuman suara** saat emosi berubah (Web Speech API, bahasa Indonesia).
- Tema **gelap/terang**, responsif untuk HP, **PWA** (bisa di-install), pintasan keyboard.
- Model dimuat di background (warm-up) sehingga server langsung menyala.
- REST API terdokumentasi, Docker, gunicorn, dan tes otomatis (pytest + GitHub Actions).

## 🚀 Menjalankan

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 emotion_api.py
```

Buka **http://localhost:5000**. (Alamat lama `/ui` otomatis dialihkan.)

> Browser hanya mengizinkan kamera di `localhost` atau lewat **HTTPS**. Untuk akses dari HP di jaringan lain, pasang di belakang reverse proxy HTTPS (mis. Caddy/nginx) atau gunakan tunnel seperti `cloudflared`.

Saat pertama dijalankan, DeepFace mengunduh bobot model (± 6 MB untuk model emosi) ke `~/.deepface`.

### Docker

```bash
docker build -t emotion-web .
docker run -p 5000:5000 -v emotion-models:/models -v emotion-data:/app/data emotion-web
```

### Produksi (gunicorn)

```bash
gunicorn -w 1 --threads 8 -t 120 -b 0.0.0.0:5000 wsgi:app
```

Gunakan 1 worker agar model hanya dimuat sekali di memori.

## ⚙️ Konfigurasi (environment variable)

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | Alamat server (`python3 emotion_api.py`) |
| `EMOTION_DETECTOR` | `opencv` | Detektor wajah default (`retinaface`, `mtcnn`, `yunet`, …) |
| `EMOTION_DB_PATH` | `data/emotions.db` | Lokasi database SQLite |
| `EMOTION_SCAN_DIR` | `scans` | Folder potongan wajah (mode kamera server) |
| `EMOTION_WARMUP` | `1` | Muat model saat start (`0` untuk menonaktifkan) |

Lihat `.env.example`.

## 🔌 REST API

| Method | Endpoint | Keterangan |
| --- | --- | --- |
| GET | `/api/health` | Status server & model |
| GET | `/api/config` | Daftar emosi & detektor |
| POST | `/api/analyze` | Analisis gambar |
| GET | `/api/history?limit=&emotion=` | Riwayat deteksi |
| DELETE | `/api/history` | Hapus riwayat |
| GET | `/api/history/export` | Unduh CSV |
| GET | `/api/stats` | Statistik agregat |

Contoh:

```bash
curl -F image=@foto.jpg -F actions=emotion -F actions=age http://localhost:5000/api/analyze
```

```json
{
  "faces": [{
    "dominant_emotion": "happy",
    "confidence": 97.3,
    "emotions": {"happy": 97.3, "neutral": 1.9, "...": 0},
    "region": {"x": 120, "y": 80, "w": 160, "h": 160},
    "age": 27
  }],
  "took_ms": 84.2, "width": 640, "height": 480, "saved": 1
}
```

`POST /api/analyze` juga menerima JSON `{"image": "data:image/jpeg;base64,...", "detector": "opencv", "save": false}`.

Endpoint lama tetap ada untuk kompatibilitas: `/camera/start`, `/camera/stop`, `/stream` (MJPEG dari kamera server), `/last`, `/history`.

## ⌨️ Pintasan

`Spasi` mulai/stop kamera · `S` snapshot · `F` layar penuh · `T` ganti tema · `,` pengaturan

## 🧪 Tes

```bash
pip install -r requirements-dev.txt
pytest -q
```

## 📁 Struktur

```
emotion_api.py      # Flask app (create_app) + route API & mode kamera server
emotion_service.py  # Wrapper DeepFace: decode gambar, analisis, normalisasi hasil
storage.py          # Riwayat SQLite (statistik, ekspor CSV)
wsgi.py             # Entry point gunicorn
templates/          # Halaman web
static/             # CSS, JS, ikon, manifest PWA, service worker, Chart.js
deepface/           # Library DeepFace (versi lokal)
main.py, analyzer.py  # Aplikasi desktop OpenCV (lama)
tests/              # Tes pytest
```
