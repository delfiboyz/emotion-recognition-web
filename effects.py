import cv2
import random
import numpy as np

def add_scanlines(frame, intensity=40, thickness=2):
    overlay = frame.copy()
    for y in range(0, frame.shape[0], thickness*2):
        cv2.line(overlay, (0, y), (frame.shape[1], y), (0, 0, 0), thickness)
    return cv2.addWeighted(overlay, intensity/100, frame, 1-intensity/100, 0)

def add_glitch(frame, frame_idx):
    h, w, _ = frame.shape
    output = frame.copy()
    if frame_idx % 7 == 0:
        for _ in range(random.randint(2, 5)):
            y1 = random.randint(0, h-25)
            y2 = y1 + random.randint(5, 25)
            shift = random.randint(-30, 30)
            output[y1:y2, :] = np.roll(output[y1:y2, :], shift, axis=1)
    return output

def add_rgb_split(frame, shift=3):
    b, g, r = cv2.split(frame)
    rows, cols = b.shape
    r_shifted = cv2.warpAffine(r, np.float32([[1, 0, shift], [0, 1, 0]]), (cols, rows))
    b_shifted = cv2.warpAffine(b, np.float32([[1, 0, -shift], [0, 1, 0]]), (cols, rows))
    return cv2.merge([b_shifted, g, r_shifted])
