import cv2
import math
import random

EMOJI_PARTICLE_COLOR = {
    "happy": (0, 255, 255),
    "sad": (255, 0, 0),
    "angry": (0, 0, 255),
    "surprise": (255, 255, 255),
    "neutral": (0, 255, 0),
    "disgust": (0, 128, 0),
    "fear": (128, 0, 128)
}
EMOJI_MODES = ["vector", "cartoon", "neon", "cyberpunk"]

class SuperEmojiRenderer:
    def __init__(self, mode="neon"):
        self.mode = mode
        self.colors = EMOJI_PARTICLE_COLOR

    def set_mode(self, mode):
        if mode in EMOJI_MODES:
            self.mode = mode

    def draw(self, frame, center, size, emotion, frame_idx):
        if self.mode == "vector":
            self._draw_vector(frame, center, size, emotion)
        elif self.mode == "cartoon":
            self._draw_cartoon(frame, center, size, emotion, frame_idx)
        elif self.mode == "neon":
            self._draw_neon(frame, center, size, emotion, frame_idx)
        elif self.mode == "cyberpunk":
            self._draw_cyberpunk(frame, center, size, emotion, frame_idx)

    # --- VECTOR MODE (minimalis, futuristik clean) ---
    def _draw_vector(self, frame, center, size, emotion):
        color = self.colors.get(emotion, (255,255,0))
        radius = size//2
        # outline saja (hologram feel)
        cv2.circle(frame, center, radius, color, 2)
        ex, ey = radius//2, radius//3
        cv2.circle(frame, (center[0]-ex, center[1]-ey), radius//8, color, -1)
        cv2.circle(frame, (center[0]+ex, center[1]-ey), radius//8, color, -1)
        mouth_y = center[1]+radius//3
        if emotion=="happy":
            cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//5),0,0,180,color,2)
        elif emotion=="sad":
            cv2.ellipse(frame,(center[0],mouth_y+radius//6),(radius//2,radius//5),0,180,360,color,2)
        elif emotion=="surprise":
            cv2.circle(frame,(center[0],mouth_y),radius//6,color,2)
        else:
            cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),color,2)

    # --- CARTOON MODE (emoji klasik + detail pipi/alis) ---
    def _draw_cartoon(self, frame, center, size, emotion, frame_idx):
        radius = size//2
        cv2.circle(frame, center, radius, (255,255,150), -1)
        ex, ey = radius//2, radius//3
        blink = (frame_idx%25)<3
        if blink:
            cv2.line(frame,(center[0]-ex-6,center[1]-ey),(center[0]-ex+6,center[1]-ey),(0,0,0),2)
            cv2.line(frame,(center[0]+ex-6,center[1]-ey),(center[0]+ex+6,center[1]-ey),(0,0,0),2)
        else:
            cv2.circle(frame,(center[0]-ex,center[1]-ey),radius//6,(0,0,0),-1)
            cv2.circle(frame,(center[0]+ex,center[1]-ey),radius//6,(0,0,0),-1)
        mouth_y = center[1]+radius//3
        if emotion=="happy":
            cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//4),0,0,180,(0,0,0),2)
            cv2.circle(frame,(center[0]-ex-10,center[1]),radius//6,(255,180,180),-1)
            cv2.circle(frame,(center[0]+ex+10,center[1]),radius//6,(255,180,180),-1)
        elif emotion=="sad":
            cv2.ellipse(frame,(center[0],mouth_y+radius//6),(radius//2,radius//4),0,180,360,(0,0,0),2)
        elif emotion=="angry":
            cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),3)
            # alis marah
            cv2.line(frame,(center[0]-ex-5,center[1]-ey-8),(center[0]-ex+5,center[1]-ey-2),(0,0,0),2)
            cv2.line(frame,(center[0]+ex-5,center[1]-ey-2),(center[0]+ex+5,center[1]-ey-8),(0,0,0),2)
        elif emotion=="surprise":
            cv2.circle(frame,(center[0],mouth_y),radius//5,(0,0,0),2)
            cv2.line(frame,(center[0]-ex-6,center[1]-ey-10),(center[0]-ex+6,center[1]-ey-6),(0,0,0),2)
            cv2.line(frame,(center[0]+ex-6,center[1]-ey-10),(center[0]+ex+6,center[1]-ey-6),(0,0,0),2)
        else:
            cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)

    # --- NEON MODE (glow + orbit statis) ---
    def _draw_neon(self, frame, center, size, emotion, frame_idx):
        radius = size//2
        color = self.colors.get(emotion,(255,255,0))
        # aura multi-layer
        for r in range(radius, radius+15, 3):
            overlay=frame.copy()
            cv2.circle(overlay,center,r,color,2)
            cv2.addWeighted(overlay,0.05,frame,0.95,0,frame)
        cv2.circle(frame,center,radius,color,-1)
        # mata + pupil
        ex, ey = radius//2,radius//3
        pupil_jitter = int(2*math.sin(frame_idx/5))
        cv2.circle(frame,(center[0]-ex,center[1]-ey),radius//6,(0,0,0),-1)
        cv2.circle(frame,(center[0]+ex,center[1]-ey),radius//6,(0,0,0),-1)
        cv2.circle(frame,(center[0]-ex+pupil_jitter,center[1]-ey),radius//12,(255,255,255),-1)
        cv2.circle(frame,(center[0]+ex+pupil_jitter,center[1]-ey),radius//12,(255,255,255),-1)
        # mulut
        mouth_y=center[1]+radius//3
        if emotion=="happy": cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//3),0,0,180,(0,0,0),3)
        elif emotion=="sad": cv2.ellipse(frame,(center[0],mouth_y+radius//5),(radius//2,radius//3),0,180,360,(0,0,0),3)
        elif emotion=="angry": cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),3)
        elif emotion=="surprise": cv2.circle(frame,(center[0],mouth_y),radius//4,(0,0,0),3)
        else: cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)
        # orbit statis
        for i in range(12):
            angle=(i*30+frame_idx*5)%360
            rad=math.radians(angle)
            px=int(center[0]+(radius+10)*math.cos(rad))
            py=int(center[1]+(radius+10)*math.sin(rad))
            cv2.circle(frame,(px,py),3,color,-1)

    # --- CYBERPUNK MODE (futuristik glowing, orbit dinamis) ---
    def _draw_cyberpunk(self, frame, center, size, emotion, frame_idx):
        radius = size//2
        base_color = self.colors.get(emotion,(255,255,0))
        # warna berdenyut (pulse sin wave)
        pulse = (math.sin(frame_idx/10)+1)/2
        color = tuple(int(c*(0.6+0.4*pulse)) for c in base_color)

        # glow hologram besar
        overlay = frame.copy()
        cv2.circle(overlay, center, radius+25, color, -1)
        cv2.addWeighted(overlay, 0.05, frame, 0.95, 0, frame)

        # lingkaran neon utama
        cv2.circle(frame, center, radius, color, 2)

        # mata hologram
        ex, ey = radius//2, radius//3
        cv2.circle(frame,(center[0]-ex,center[1]-ey),radius//7,color,2)
        cv2.circle(frame,(center[0]+ex,center[1]-ey),radius//7,color,2)

        # mulut hologram
        mouth_y=center[1]+radius//3
        if emotion=="happy":
            cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//5),0,0,180,color,2)
        elif emotion=="sad":
            cv2.ellipse(frame,(center[0],mouth_y+radius//6),(radius//2,radius//5),0,180,360,color,2)
        elif emotion=="surprise":
            cv2.circle(frame,(center[0],mouth_y),radius//5,color,2)
        else:
            cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),color,2)

        # partikel orbit dinamis
        for i in range(16):
            angle = (i*22.5 + frame_idx*8) % 360
            rad = math.radians(angle)
            orbit_r = radius + 20 + int(5*math.sin(frame_idx/15 + i))
            px = int(center[0] + orbit_r*math.cos(rad))
            py = int(center[1] + orbit_r*math.sin(rad))
            intensity = int(150 + 105*math.sin(frame_idx/10 + i))
            glow_color = (min(255,color[0]), min(255,intensity), min(255,color[2]))
            cv2.circle(frame, (px, py), 3, glow_color, -1)
