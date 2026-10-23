import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from emotion_service import EmotionAnalyzer  # noqa: E402


class StubDeepFace:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def analyze(self, img, **kwargs):
        self.kwargs = kwargs
        return self.result


def make_analyzer(result):
    a = EmotionAnalyzer()
    a._deepface = StubDeepFace(result)
    return a


def test_normalizes_faces_and_sorts_left_to_right():
    a = make_analyzer([
        {"dominant_emotion": "sad", "emotion": {"sad": np.float32(80.123), "happy": 19.877},
         "face_confidence": 0.9, "region": {"x": 200, "y": 10, "w": 40, "h": 40}},
        {"dominant_emotion": "happy", "emotion": {"happy": 99.0}, "face_confidence": 0.95,
         "region": {"x": 5, "y": 10, "w": 40, "h": 40}, "age": 31.4, "dominant_gender": "Woman"},
    ])
    out = a.analyze(np.zeros((240, 320, 3), np.uint8), actions=["age", "bogus"], detector_backend="nope")
    assert [f["dominant_emotion"] for f in out["faces"]] == ["happy", "sad"]
    assert out["faces"][0]["age"] == 31 and out["faces"][0]["gender"] == "female"
    assert out["faces"][1]["confidence"] == 80.12
    assert a._deepface.kwargs["actions"] == ["emotion", "age"]
    assert a._deepface.kwargs["detector_backend"] == "opencv"


def test_drops_full_frame_result_when_no_face():
    a = make_analyzer([{"dominant_emotion": "neutral", "emotion": {"neutral": 60.0}, "face_confidence": 0,
                        "region": {"x": 0, "y": 0, "w": 320, "h": 240}}])
    assert a.analyze(np.zeros((240, 320, 3), np.uint8))["faces"] == []
