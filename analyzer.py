import cv2
import time
import os
import csv
from deepface import DeepFace
from renderer import SuperEmojiRenderer
from emoji import UltraEmoji

from config import *
from effects import add_scanlines, add_glitch, add_rgb_split


def analyze_simple_vector():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return

    # === Folder & File Penyimpanan ===
    os.makedirs("scans", exist_ok=True)
    csv_path = "scans/emotions_log.csv"

    if not os.path.exists(csv_path):
        with open(csv_path, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "emotion", "filename"])

    # === Window ===
    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_TITLE, WINDOW_SIZE[0], WINDOW_SIZE[1])

    frame_idx = 0
    fps_start = time.time()
    emojis = []
    renderer = SuperEmojiRenderer(mode=EMOJI_MODES[EMOJI_MODE_IDX])
    effects_enabled = False
    results = []
    last_scan_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        fh, fw = frame.shape[:2]

        try:
            results = DeepFace.analyze(
                frame, actions=["emotion"], enforce_detection=False
            )
            if not isinstance(results, list):
                results = [results]

            if len(results) == 0:
                emojis = []
            else:
                if len(emojis) != len(results):
                    emojis = [
                        UltraEmoji(
                            r["dominant_emotion"],
                            r["region"]["x"],
                            r["region"]["y"],
                            r["region"]["w"],
                            r["region"]["h"],
                        )
                        for r in results
                    ]

                for idx, r in enumerate(results):
                    x, y, ww, hh = map(
                        int,
                        (
                            r["region"]["x"],
                            r["region"]["y"],
                            r["region"]["w"],
                            r["region"]["h"],
                        ),
                    )
                    dominant = r["dominant_emotion"]

                    emojis[idx].update(x, y, ww, hh)
                    emojis[idx].emotion = dominant

                    # Kotak wajah & label emosi
                    cv2.rectangle(frame, (x, y), (x + ww, y + hh), (0, 255, 255), 2)
                    color = renderer.colors.get(dominant, (0, 255, 255))
                    cv2.putText(
                        frame,
                        dominant.upper(),
                        (x, max(y - 8, 16)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

                    # Auto Scan setiap 1 detik
                    current_time = time.time()
                    if current_time - last_scan_time >= 1.0:
                        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                        filename = f"scans/{timestamp}_{dominant}.jpg"
                        face_crop = frame[y : y + hh, x : x + ww]
                        if face_crop.size > 0:
                            cv2.imwrite(filename, face_crop)
                            with open(csv_path, mode="a", newline="") as f:
                                csv.writer(f).writerow([timestamp, dominant, filename])
                        last_scan_time = current_time
        except Exception:
            pass

        # === Render emoji kecil kiri atas ===
        current_emotion = emojis[0].emotion if emojis else "neutral"
        emoji_x, emoji_y = 40, 70
        emoji_size = 55  # sedikit lebih kecil agar seimbang
        renderer.draw(frame, (emoji_x, emoji_y), emoji_size, current_emotion, frame_idx)

        # === Label kecil di bawah emoji ===
        label_text = f"Emosi Dominan: {current_emotion.upper()}"
        label_scale = 0.45
        label_thickness = 1
        color = renderer.colors.get(current_emotion, (0, 255, 255))

        label_size = cv2.getTextSize(
            label_text, cv2.FONT_HERSHEY_SIMPLEX, label_scale, label_thickness
        )[0]
        label_x = emoji_x + (emoji_size // 2) - (label_size[0] // 2)
        label_y = emoji_y + emoji_size + 18

        overlay = frame.copy()
        bg_padding = 4
        bg_top_left = (label_x - bg_padding, label_y - label_size[1] - bg_padding)
        bg_bottom_right = (label_x + label_size[0] + bg_padding, label_y + bg_padding)
        cv2.rectangle(overlay, bg_top_left, bg_bottom_right, (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        cv2.putText(
            frame,
            label_text,
            (label_x, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            label_scale,
            color,
            label_thickness + 1,
            cv2.LINE_AA,
        )

        # === Info sejajar ke kanan emoji ===
        fps = frame_idx / (time.time() - fps_start + 1e-6)
        text_y = emoji_y + 20
        info_texts = [
            f"FPS: {fps:.2f}",
            f"Mode: {renderer.mode.upper()}",
            f"Effects: {'ON' if effects_enabled else 'OFF'}",
        ]
        x_offset = emoji_x + emoji_size + 25
        for t in info_texts:
            cv2.putText(
                frame,
                t,
                (x_offset, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (200, 255, 200),
                1,
                cv2.LINE_AA,
            )
            # Jarak antar teks horizontal
            x_offset += cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0][0] + 35

        # === Kontrol di bawah layar ===
        cv2.putText(
            frame,
            "Controls: Q=quit | 1-4=mode | F=effects",
            (12, fh - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 180, 180),
            1,
        )

        # === Efek opsional ===
        if effects_enabled:
            frame = add_scanlines(frame, 25, 2)
            frame = add_glitch(frame, frame_idx)
            frame = add_rgb_split(frame, 2)

        cv2.imshow(WINDOW_TITLE, frame)

        # === Keyboard Controls ===
        key = cv2.waitKey(1)
        if key & 0xFF == ord("q"):
            break
        elif key & 0xFF in [ord("1"), ord("2"), ord("3"), ord("4")]:
            renderer.set_mode(EMOJI_MODES[int(chr(key & 0xFF)) - 1])
        elif key & 0xFF == ord("f"):
            effects_enabled = not effects_enabled

    cap.release()
    cv2.destroyAllWindows()
