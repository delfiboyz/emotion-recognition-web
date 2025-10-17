import cv2
import json
import os
import numpy as np
from datetime import datetime
import time

SAVE_DIR = "scans"
os.makedirs(SAVE_DIR, exist_ok=True)

def scan_animation(frame, region, window_title="Ultra Emoji + Emotion Scanner"):
    """
    Efek scan futuristik di dalam jendela utama (tanpa jendela baru).
    """
    x, y, w, h = map(int, region)

    for i in range(y, y + h, 6):
        overlay = frame.copy()

        # Garis scan utama
        cv2.line(overlay, (x, i), (x + w, i), (0, 255, 255), 2)

        # Efek glow pada area scan
        face_area = overlay[y:y+h, x:x+w].copy()
        mask = np.zeros_like(face_area)
        yy = i - y
        if 0 <= yy < h:
            cv2.line(mask, (0, yy), (w, yy), (0, 255, 255), 2)
            glow = cv2.GaussianBlur(mask, (13, 13), 0)
            face_area = cv2.addWeighted(face_area, 1.0, glow, 0.5, 0)
            overlay[y:y+h, x:x+w] = face_area

        # Gabungkan efek ke frame utama
        blended = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        # Tampilkan hasil di jendela utama
        cv2.imshow(window_title, blended)
        cv2.waitKey(10)

    # Flash akhir (efek pemindaian selesai)
    flash = frame.copy()
    cv2.rectangle(flash, (x, y), (x + w, y + h), (0, 255, 255), -1)
    blended = cv2.addWeighted(flash, 0.2, frame, 0.8, 0)
    cv2.imshow(window_title, blended)
    cv2.waitKey(80)

def save_scanned_frame(frame, result):
    """
    Simpan seluruh frame + JSON hasil emosi.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dominant = result['dominant_emotion']
    region = result['region']
    emotions = result.get('emotion', {})

    img_name = f"scan_{timestamp}_{dominant}.png"
    json_name = f"scan_{timestamp}_{dominant}.json"

    img_path = os.path.join(SAVE_DIR, img_name)
    json_path = os.path.join(SAVE_DIR, json_name)

    # Simpan frame penuh
    cv2.imwrite(img_path, frame)

    # Simpan metadata JSON
    data = {
        "timestamp": timestamp,
        "dominant_emotion": dominant,
        "region": region,
        "emotions": emotions
    }
    with open(json_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"[💾] Frame + JSON saved: {img_name}")
