# ultra_emoji_with_scatter.py
from deepface import DeepFace
import cv2
import time
import numpy as np
import math
import random


# ---------------- Emoji object with scatter/tether behaviour ----------------
class UltraEmoji:
    def __init__(self, emotion,x,y,w,h):
        self.emotion=emotion
        # compute two sizes: when on-face (inside box) and when outside
        face_min = max(20, int(min(w,h)))
        self.size_inside = max(48, int(face_min * 0.95))  # roughly equal to face size (95%)
        self.size_outside = max(30, int(self.size_inside * 0.62))  # slightly smaller when outside
        self.base_size = self.size_inside

        # anchored center (face center)
        self.anchor_x=x+w//2
        self.anchor_y=y+h//2
        # current position starts anchored
        self.x=float(self.anchor_x)
        self.y=float(self.anchor_y)
        self.phase=random.uniform(0,2*math.pi)
        self.float_speed=random.uniform(0.03,0.10)
        # scatter target relative to anchor
        self.target_dx=0.0
        self.target_dy=0.0
        self.scatter_speed=random.uniform(0.8,2.2)  # pixels per frame (unused for snap)
        self.scatter_radius_min=20
        self.scatter_radius_max=max(60, int(min(w,h)*1.0))
        self.is_scattered=False
        # remember last face size for computing "outside box" targets
        self.last_w = w
        self.last_h = h

    def pick_new_target_outside_box(self):
        """Pick a target just outside the face bounding box so emoji does NOT overlap.
        Chooses a side (top/bottom/left/right) and a random position along that side,
        then offsets so the emoji circle is placed entirely outside the rectangle.
        """
        w = max(20, self.last_w)
        h = max(20, self.last_h)
        # use the outside size to ensure no overlap
        radius = max(12, self.size_outside // 2)
        gap = max(6, int(min(w,h)*0.12))

        # margin outside the box (scale with face size and emoji radius)
        margin = int(max(gap + radius, min(w,h)*0.35))

        side = random.choice(['top','bottom','left','right'])
        if side == 'top':
            jitter = random.uniform(-0.35,0.35) * w
            self.target_dx = int(jitter)
            self.target_dy = - (h//2 + margin)
        elif side == 'bottom':
            jitter = random.uniform(-0.35,0.35) * w
            self.target_dx = int(jitter)
            self.target_dy = (h//2 + margin)
        elif side == 'left':
            jitter = random.uniform(-0.35,0.35) * h
            self.target_dx = - (w//2 + margin)
            self.target_dy = int(jitter)
        else:  # right
            jitter = random.uniform(-0.35,0.35) * h
            self.target_dx = (w//2 + margin)
            self.target_dy = int(jitter)

    def update(self,x=None,y=None,w=None,h=None,scatter=False):
        self.phase+=self.float_speed
        # update anchor and sizes if face moved
        if x is not None and y is not None and w is not None and h is not None:
            self.anchor_x = x + w//2
            self.anchor_y = y + h//2
            face_min = max(20, int(min(w,h)))
            self.size_inside = max(48, int(face_min * 0.95))
            self.size_outside = max(30, int(self.size_inside * 0.62))
            self.last_w = w
            self.last_h = h
            # if currently scattered, ensure target margin updated
            self.scatter_radius_max = max(60, int(min(w,h)*1.0))

        # tiny bobbing
        float_x=int(2*math.sin(self.phase))
        float_y=int(1*math.sin(self.phase/2))

        if scatter:
            # use outside size
            self.base_size = self.size_outside
            if not self.is_scattered or (self.target_dx==0 and self.target_dy==0):
                self.pick_new_target_outside_box()
                self.is_scattered=True
            tgt_x = self.anchor_x + self.target_dx
            tgt_y = self.anchor_y + self.target_dy
            # snap to target with tiny bob
            self.x = tgt_x + float_x*0.12
            self.y = tgt_y + float_y*0.12

            # safety: if any overlap, push outward
            half_w = self.last_w/2
            half_h = self.last_h/2
            dx_from_anchor = self.x - self.anchor_x
            dy_from_anchor = self.y - self.anchor_y
            if abs(dx_from_anchor) < half_w and abs(dy_from_anchor) < half_h:
                if abs(dx_from_anchor) >= abs(dy_from_anchor):
                    push = (half_w + max(8, self.base_size//2)) * (1 if dx_from_anchor >= 0 else -1)
                    self.x = self.anchor_x + push
                else:
                    push = (half_h + max(8, self.base_size//2)) * (1 if dy_from_anchor >= 0 else -1)
                    self.y = self.anchor_y + push
        else:
            # on-face: use inside size and tether smoothly to face center
            self.base_size = self.size_inside
            tgt_x = self.anchor_x + int(6*math.sin(self.phase))
            tgt_y = self.anchor_y + int(4*math.sin(self.phase/2))
            ease = 0.25
            self.x = self.x*(1-ease) + tgt_x*ease
            self.y = self.y*(1-ease) + tgt_y*ease
            self.is_scattered=False
