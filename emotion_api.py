"""Emotion Recognition Web - server Flask.

Mode utama: kamera dibuka di browser (getUserMedia) lalu frame dikirim ke
POST /api/analyze. Mode lama (kamera di server + MJPEG /stream) tetap tersedia.
"""

import os
import threading
import time

import cv2
from flask import Flask, Response, jsonify, redirect, render_template, request, send_from_directory

try:
    from flask_cors import CORS
except ImportError:  # flask-cors opsional
    CORS = None

from emotion_service import (
    DETECTOR_BACKENDS, EMOTIONS, EmotionAnalyzer, ImageDecodeError, decode_image,
)
from storage import EmotionStore, now_iso

DEFAULT_CONFIG = {
    "DB_PATH": os.environ.get("EMOTION_DB_PATH", "data/emotions.db"),
    "SCAN_DIR": os.environ.get("EMOTION_SCAN_DIR", "scans"),
    "DETECTOR_BACKEND": os.environ.get("EMOTION_DETECTOR", "opencv"),
    "WARMUP": os.environ.get("EMOTION_WARMUP", "1") == "1",
    "MAX_CONTENT_LENGTH": 8 * 1024 * 1024,
}


# ===============================
# MODE LAMA: KAMERA DI SERVER
# ===============================
class ServerCamera:
    def __init__(self, analyzer, store, scan_dir):
        self.analyzer = analyzer
        self.store = store
        self.scan_dir = scan_dir
        self.lock = threading.Lock()
        self.frame = None
        self.running = False
        self.last = {"timestamp": None, "emotion": "neutral", "filename": None, "region": None}
        self._renderer = None

    def start(self):
        if self.running:
            return False
        self.running = True
        threading.Thread(target=self._capture, daemon=True).start()
        threading.Thread(target=self._analyze_loop, daemon=True).start()
        return True

    def stop(self):
        if not self.running:
            return False
        self.running = False
        return True

    def _capture(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Kamera gagal dibuka")
            self.running = False
            return
        print("📷 Kamera dinyalakan")
        while self.running:
            ret, frame = cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            time.sleep(0.01)
        cap.release()
        with self.lock:
            self.frame = None
        print("📷 Kamera dimatikan")

    def _analyze_loop(self):
        os.makedirs(self.scan_dir, exist_ok=True)
        while self.running:
            with self.lock:
                frame = None if self.frame is None else self.frame.copy()
            if frame is None:
                time.sleep(0.1)
                continue
            try:
                faces = self.analyzer.analyze(frame)["faces"]
            except Exception as e:
                print("[DeepFace Warning]", e)
                time.sleep(1)
                continue
            if faces:
                face = faces[0]
                r = face["region"]
                stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                filename = os.path.join(self.scan_dir, f"{stamp}_{face['dominant_emotion']}.jpg")
                crop = frame[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
                if crop.size > 0:
                    cv2.imwrite(filename, crop)
                with self.lock:
                    self.last = {
                        "timestamp": stamp,
                        "emotion": face["dominant_emotion"],
                        "filename": filename,
                        "region": (r["x"], r["y"], r["w"], r["h"]),
                    }
                self.store.add_faces(faces, source="server", snapshot=filename)
            time.sleep(1.0)

    def stream(self):
        if self._renderer is None:
            from renderer import SuperEmojiRenderer
            self._renderer = SuperEmojiRenderer(mode="neon")
        frame_count = 0
        while self.running:
            with self.lock:
                frame = None if self.frame is None else self.frame.copy()
                emotion = self.last["emotion"]
                region = self.last["region"]
            if frame is None:
                time.sleep(0.1)
                continue
            if region:
                x, y, w, h = region
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, emotion.upper(), (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            self._renderer.draw(frame, (40, 70), 55, emotion, frame_count)
            ok, buffer = cv2.imencode(".jpg", frame)
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            frame_count += 1
            time.sleep(0.03)


# ===============================
# APP FACTORY
# ===============================
def create_app(config=None, analyzer=None, store=None):
    app = Flask(__name__)
    app.config.update(DEFAULT_CONFIG)
    app.config.update(config or {})
    if CORS:
        CORS(app, resources={r"/api/*": {"origins": "*"}})

    analyzer = analyzer or EmotionAnalyzer(app.config["DETECTOR_BACKEND"])
    store = store or EmotionStore(app.config["DB_PATH"])
    camera = ServerCamera(analyzer, store, app.config["SCAN_DIR"])
    app.extensions["analyzer"] = analyzer
    app.extensions["store"] = store
    if app.config["WARMUP"] and hasattr(analyzer, "warmup_async"):
        analyzer.warmup_async()

    def error(message, status=400):
        return jsonify({"error": message}), status

    # ---------- Front-end ----------
    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/sw.js")
    def service_worker():
        # Disajikan dari root agar scope service worker mencakup seluruh app.
        resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.get("/ui")
    def ui():
        return redirect("/", code=301)

    # ---------- REST API ----------
    @app.get("/api")
    def api_index():
        return jsonify({
            "message": "Emotion Recognition API",
            "routes": {
                "GET /api/health": "Status server & model",
                "GET /api/config": "Daftar emosi & detektor",
                "POST /api/analyze": "Analisis gambar (multipart 'image' atau JSON {image: dataURL})",
                "GET /api/history": "Riwayat deteksi (?limit=&emotion=)",
                "DELETE /api/history": "Hapus riwayat",
                "GET /api/history/export": "Unduh riwayat CSV",
                "GET /api/stats": "Statistik agregat",
                "GET /stream": "MJPEG kamera server (mode lama)",
            },
        })

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "model_ready": bool(getattr(analyzer, "ready", True)),
            "model_error": getattr(analyzer, "error", None),
            "server_camera": camera.running,
            "time": now_iso(),
        })

    @app.get("/api/config")
    def api_config():
        return jsonify({
            "emotions": EMOTIONS,
            "detectors": DETECTOR_BACKENDS,
            "default_detector": app.config["DETECTOR_BACKEND"],
        })

    @app.post("/api/analyze")
    def analyze():
        opts = {}
        if "image" in request.files:
            raw = request.files["image"].read()
            opts = request.form.to_dict()
            actions = request.form.getlist("actions") or ["emotion"]
        else:
            body = request.get_json(silent=True) or {}
            raw = body.get("image")
            opts = body
            actions = body.get("actions") or ["emotion"]
        if not raw:
            return error("Field 'image' wajib diisi")
        if isinstance(actions, str):
            actions = [a.strip() for a in actions.split(",")]
        try:
            img = decode_image(raw)
        except ImageDecodeError as e:
            return error(str(e))
        try:
            result = analyzer.analyze(img, actions=actions, detector_backend=opts.get("detector"))
        except Exception as e:
            app.logger.exception("Analisis gagal")
            return error(f"Analisis gagal: {e}", 500)

        save = str(opts.get("save", "true")).lower() not in ("0", "false", "no")
        result["saved"] = 0
        if save and result["faces"]:
            result["saved"] = store.add_faces(result["faces"], source=opts.get("source", "browser"))
        result["timestamp"] = now_iso()
        return jsonify(result)

    @app.get("/api/history")
    def api_history():
        limit = min(max(request.args.get("limit", 100, type=int), 1), 5000)
        return jsonify(store.recent(limit=limit, emotion=request.args.get("emotion") or None))

    @app.delete("/api/history")
    def api_history_clear():
        return jsonify({"deleted": store.clear()})

    @app.get("/api/history/export")
    def api_history_export():
        filename = f"emotion_history_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            store.export_csv(), mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.get("/api/stats")
    def api_stats():
        return jsonify(store.stats())

    @app.errorhandler(413)
    def too_large(_):
        return error("Ukuran gambar maksimal 8 MB", 413)

    # ---------- Endpoint lama (kompatibel) ----------
    @app.get("/stream")
    def stream():
        return Response(camera.stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/camera/start")
    def camera_start():
        return jsonify({"status": "Camera started" if camera.start() else "Camera already on"})

    @app.get("/camera/stop")
    def camera_stop():
        return jsonify({"status": "Camera stopped" if camera.stop() else "Camera already off"})

    @app.get("/last")
    def last():
        with camera.lock:
            return jsonify(camera.last)

    @app.get("/history")
    def history():
        return jsonify(store.recent(limit=1000))

    return app


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Emotion Recognition Web siap di http://127.0.0.1:{port}")
    create_app().run(host=host, port=port, threaded=True)
