from flask import Flask, Response, jsonify, render_template
import threading
import cv2, time, csv, os
from deepface import DeepFace
from renderer import SuperEmojiRenderer
from emoji import UltraEmoji
from config import *
from effects import add_scanlines, add_glitch, add_rgb_split

app = Flask(__name__)

# Folder log
os.makedirs("scans", exist_ok=True)
CSV_PATH = "scans/emotions_log.csv"
if not os.path.exists(CSV_PATH):
    with open(CSV_PATH, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp", "emotion", "filename"])

# Global variables
cap = None
current_frame = None
last_emotion = {
    "timestamp": None,
    "emotion": "neutral",
    "filename": None,
    "region": None,
}
lock = threading.Lock()
renderer = SuperEmojiRenderer(mode=EMOJI_MODES[EMOJI_MODE_IDX])
stop_threads = False
threads = []

# Kamera ON/OFF controller
camera_on = False


# ===============================
# THREADS
# ===============================
def camera_capture():
    global cap, current_frame, stop_threads
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Kamera gagal dibuka")
        return
    print("📷 Kamera dinyalakan")
    while not stop_threads:
        ret, frame = cap.read()
        if ret:
            with lock:
                current_frame = frame.copy()
        time.sleep(0.01)
    cap.release()
    print("📷 Kamera dimatikan")


def emotion_analyzer():
    global current_frame, last_emotion, stop_threads
    last_scan_time = 0
    while not stop_threads:
        with lock:
            frame_copy = None if current_frame is None else current_frame.copy()
        if frame_copy is not None and (time.time() - last_scan_time >= 1.0):
            try:
                result = DeepFace.analyze(
                    frame_copy, actions=["emotion"], enforce_detection=False
                )
                if not isinstance(result, list):
                    result = [result]
                if len(result) > 0:
                    r = result[0]
                    dominant = r["dominant_emotion"]
                    x, y, w, h = map(
                        int,
                        (
                            r["region"]["x"],
                            r["region"]["y"],
                            r["region"]["w"],
                            r["region"]["h"],
                        ),
                    )
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"scans/{timestamp}_{dominant}.jpg"
                    face_crop = frame_copy[y : y + h, x : x + w]
                    if face_crop.size > 0:
                        cv2.imwrite(filename, face_crop)
                    with lock:
                        last_emotion.update(
                            {
                                "timestamp": timestamp,
                                "emotion": dominant,
                                "filename": filename,
                                "region": (x, y, w, h),
                            }
                        )
                    with open(CSV_PATH, "a", newline="") as f:
                        csv.writer(f).writerow([timestamp, dominant, filename])
                    last_scan_time = time.time()
            except Exception as e:
                print("[DeepFace Warning]", e)
        time.sleep(0.1)


# ===============================
# STREAM GENERATOR
# ===============================
def generate_stream():
    frame_count = 0
    while True:
        if not camera_on or current_frame is None:
            time.sleep(0.1)
            continue
        with lock:
            frame = current_frame.copy()
            emotion = last_emotion.get("emotion", "neutral")
            region = last_emotion.get("region")
        if region:
            x, y, w, h = region
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                frame,
                emotion.upper(),
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
        renderer.draw(frame, (40, 70), 55, emotion, frame_count)
        color = renderer.colors.get(emotion, (0, 255, 255))
        cv2.putText(
            frame,
            f"Emosi: {emotion.upper()}",
            (40, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            continue
        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
        frame_count += 1
        time.sleep(0.03)


# ===============================
# ROUTES
# ===============================
@app.route("/")
def index():
    return jsonify(
        {
            "message": "Emotion Detection API",
            "routes": {
                "/stream": "Live MJPEG stream",
                "/camera/start": "Turn on camera",
                "/camera/stop": "Turn off camera",
                "/last": "Get last detected emotion",
                "/history": "Full log",
                "/ui": "Web front-end",
            },
        }
    )


@app.route("/stream")
def stream():
    return Response(
        generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/camera/start")
def camera_start():
    global camera_on, stop_threads, threads
    if camera_on:
        return jsonify({"status": "Camera already on"})
    stop_threads = False
    t1 = threading.Thread(target=camera_capture, daemon=True)
    t2 = threading.Thread(target=emotion_analyzer, daemon=True)
    t1.start()
    t2.start()
    threads = [t1, t2]
    camera_on = True
    return jsonify({"status": "Camera started"})


@app.route("/camera/stop")
def camera_stop():
    global camera_on, stop_threads
    if not camera_on:
        return jsonify({"status": "Camera already off"})
    stop_threads = True
    camera_on = False
    return jsonify({"status": "Camera stopped"})


@app.route("/last")
def last():
    with lock:
        return jsonify(last_emotion)


@app.route("/history")
def history():
    data = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r") as f:
            data = list(csv.DictReader(f))
    return jsonify(data)


# ===============================
# FRONT-END
# ===============================
@app.route("/ui")
def ui():
    return render_template("index.html")  # pastikan file templates/index.html ada


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    print("API ready at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)
