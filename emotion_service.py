"""Lapisan analisis emosi di atas DeepFace.

DeepFace (dan TensorFlow) baru di-import saat pertama dipakai sehingga server
bisa langsung menyala dan model dimuat di background (warm-up).
"""

import base64
import binascii
import threading
import time

import cv2
import numpy as np

EMOTIONS = ["happy", "sad", "angry", "surprise", "neutral", "disgust", "fear"]
DETECTOR_BACKENDS = [
    "opencv", "ssd", "mtcnn", "fastmtcnn", "retinaface",
    "mediapipe", "yolov8", "yolov11n", "yunet", "centerface",
]
ALLOWED_ACTIONS = {"emotion", "age", "gender"}
MAX_SIDE = 960


class ImageDecodeError(ValueError):
    pass


def decode_image(data):
    """Ubah bytes / data URL / base64 menjadi gambar BGR numpy."""
    if isinstance(data, str):
        if data.startswith("data:"):
            data = data.split(",", 1)[-1]
        try:
            data = base64.b64decode(data, validate=False)
        except (binascii.Error, ValueError) as e:
            raise ImageDecodeError("base64 tidak valid") from e
    if not data:
        raise ImageDecodeError("gambar kosong")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ImageDecodeError("format gambar tidak dikenali")
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def _normalize_face(raw):
    region = raw.get("region") or {}
    emotions = {k: round(float(v), 2) for k, v in (raw.get("emotion") or {}).items()}
    dominant = raw.get("dominant_emotion") or (max(emotions, key=emotions.get) if emotions else "neutral")
    face = {
        "dominant_emotion": dominant,
        "confidence": emotions.get(dominant, 0.0),
        "emotions": emotions,
        "face_confidence": round(float(raw.get("face_confidence", 0) or 0), 3),
        "region": {k: int(region.get(k, 0) or 0) for k in ("x", "y", "w", "h")},
    }
    if "age" in raw:
        face["age"] = int(raw["age"])
    if "dominant_gender" in raw:
        face["gender"] = "male" if raw["dominant_gender"] == "Man" else "female"
    return face


class EmotionAnalyzer:
    def __init__(self, detector_backend="opencv"):
        self.detector_backend = detector_backend
        self._deepface = None
        self._lock = threading.Lock()
        self.ready = False
        self.error = None

    def _load(self):
        if self._deepface is None:
            from deepface import DeepFace
            self._deepface = DeepFace
        return self._deepface

    def warmup(self):
        """Muat model emosi lebih awal supaya request pertama tidak lambat."""
        try:
            self.analyze(np.zeros((224, 224, 3), np.uint8))
            self.ready = True
        except Exception as e:  # pragma: no cover - tergantung lingkungan
            self.error = str(e)
            print("[Warmup gagal]", e)

    def warmup_async(self):
        threading.Thread(target=self.warmup, daemon=True).start()

    def analyze(self, img, actions=("emotion",), detector_backend=None):
        actions = [a for a in actions if a in ALLOWED_ACTIONS] or ["emotion"]
        if "emotion" not in actions:
            actions.insert(0, "emotion")
        backend = detector_backend if detector_backend in DETECTOR_BACKENDS else self.detector_backend
        DeepFace = self._load()
        start = time.perf_counter()
        # Model Keras tidak aman dipanggil paralel, jadi serialkan.
        with self._lock:
            result = DeepFace.analyze(
                img, actions=actions, detector_backend=backend,
                enforce_detection=False, silent=True,
            )
        took_ms = round((time.perf_counter() - start) * 1000, 1)
        self.ready = True
        if not isinstance(result, list):
            result = [result]
        h, w = img.shape[:2]
        faces = []
        for raw in result:
            face = _normalize_face(raw)
            r = face["region"]
            # Tanpa enforce_detection DeepFace mengembalikan seluruh frame saat
            # tidak ada wajah; buang hasil semacam itu.
            if face["face_confidence"] == 0 and r["w"] >= w - 1 and r["h"] >= h - 1:
                continue
            faces.append(face)
        faces.sort(key=lambda f: f["region"]["x"])
        return {"faces": faces, "took_ms": took_ms, "width": w, "height": h, "detector": backend}
