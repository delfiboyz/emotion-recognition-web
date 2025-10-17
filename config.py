import os

# UI & Mode
WINDOW_TITLE = "Ultra Emoji + Emotion Scanner (with Save)"
WINDOW_SIZE = (1280, 720)
BAR_WIDTH = 180
BAR_MAX_PIXELS = 160
EMOJI_MODE_IDX = 2
EMOTIONS_ORDER = ["happy", "sad", "angry", "surprise", "neutral", "disgust", "fear"]
EMOJI_MODES = ["vector", "cartoon", "neon", "cyberpunk"]

# Direktori penyimpanan hasil scan
SAVE_DIR = "scanned_faces"
os.makedirs(SAVE_DIR, exist_ok=True)
