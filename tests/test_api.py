import io
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from emotion_api import create_app  # noqa: E402
from storage import EmotionStore  # noqa: E402


class FakeAnalyzer:
    ready = True
    error = None

    def __init__(self, faces=None):
        self.calls = []
        self.faces = faces if faces is not None else [{
            "dominant_emotion": "happy",
            "confidence": 91.5,
            "emotions": {"happy": 91.5, "neutral": 5.0, "sad": 3.5},
            "face_confidence": 0.98,
            "region": {"x": 10, "y": 20, "w": 50, "h": 50},
        }]

    def analyze(self, img, actions=("emotion",), detector_backend=None):
        self.calls.append({"shape": img.shape, "actions": list(actions), "detector": detector_backend})
        h, w = img.shape[:2]
        return {"faces": self.faces, "took_ms": 1.0, "width": w, "height": h, "detector": detector_backend or "opencv"}


def jpeg_bytes(w=320, h=240):
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 127, np.uint8))
    assert ok
    return buf.tobytes()


@pytest.fixture
def analyzer():
    return FakeAnalyzer()


@pytest.fixture
def client(analyzer):
    app = create_app({"TESTING": True, "WARMUP": False}, analyzer=analyzer, store=EmotionStore(":memory:"))
    return app.test_client()


def test_ui_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/ui").status_code == 301
    assert client.get("/sw.js").status_code == 200
    health = client.get("/api/health").get_json()
    assert health["status"] == "ok" and health["model_ready"] is True
    cfg = client.get("/api/config").get_json()
    assert "happy" in cfg["emotions"] and "opencv" in cfg["detectors"]


def test_analyze_multipart_saves_history(client, analyzer):
    res = client.post("/api/analyze", data={
        "image": (io.BytesIO(jpeg_bytes()), "frame.jpg"),
        "actions": ["emotion", "age"],
        "detector": "retinaface",
    }, content_type="multipart/form-data")
    body = res.get_json()
    assert res.status_code == 200
    assert body["faces"][0]["dominant_emotion"] == "happy"
    assert body["saved"] == 1 and (body["width"], body["height"]) == (320, 240)
    assert analyzer.calls[0]["actions"] == ["emotion", "age"]
    assert analyzer.calls[0]["detector"] == "retinaface"

    rows = client.get("/api/history").get_json()
    assert len(rows) == 1 and rows[0]["emotion"] == "happy" and rows[0]["scores"]["happy"] == 91.5
    stats = client.get("/api/stats").get_json()
    assert stats["total"] == 1 and stats["by_emotion"]["happy"]["count"] == 1


def test_analyze_json_data_url_without_save(client):
    import base64
    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes()).decode()
    res = client.post("/api/analyze", json={"image": data_url, "save": False})
    assert res.status_code == 200 and res.get_json()["saved"] == 0
    assert client.get("/api/history").get_json() == []


def test_large_images_are_downscaled(client, analyzer):
    client.post("/api/analyze", data={"image": (io.BytesIO(jpeg_bytes(1920, 1080)), "big.jpg")},
                content_type="multipart/form-data")
    h, w = analyzer.calls[0]["shape"][:2]
    assert max(h, w) == 960


@pytest.mark.parametrize("payload", [{}, {"image": "bukan-gambar"}])
def test_analyze_rejects_bad_input(client, payload):
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 400 and "error" in res.get_json()


def test_history_filter_export_and_clear(client):
    for _ in range(2):
        client.post("/api/analyze", data={"image": (io.BytesIO(jpeg_bytes()), "f.jpg")},
                    content_type="multipart/form-data")
    assert len(client.get("/api/history?emotion=happy").get_json()) == 2
    assert client.get("/api/history?emotion=sad").get_json() == []

    csv_res = client.get("/api/history/export")
    assert csv_res.mimetype == "text/csv"
    assert csv_res.data.decode().count("\n") == 3  # header + 2 baris

    assert client.delete("/api/history").get_json()["deleted"] == 2
    assert client.get("/api/stats").get_json()["total"] == 0


def test_legacy_routes(client):
    assert client.get("/last").get_json()["emotion"] == "neutral"
    assert client.get("/history").status_code == 200
    assert client.get("/camera/stop").get_json()["status"] == "Camera already off"
