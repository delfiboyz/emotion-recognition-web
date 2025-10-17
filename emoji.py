import random
import math

class UltraEmoji:
    def __init__(self, emotion,x,y,w,h):
        self.emotion=emotion
        face_min = max(20, int(min(w,h)))
        self.size_inside = max(48, int(face_min * 0.95))
        self.size_outside = max(30, int(self.size_inside * 0.62))
        self.base_size = self.size_inside
        self.anchor_x=x+w//2
        self.anchor_y=y+h//2
        self.x=float(self.anchor_x)
        self.y=float(self.anchor_y)
        self.phase=random.uniform(0,2*math.pi)
        self.float_speed=random.uniform(0.03,0.10)
        self.target_dx=0.0
        self.target_dy=0.0
        self.scatter_speed=random.uniform(0.8,2.2)
        self.scatter_radius_min=20
        self.scatter_radius_max=max(60, int(min(w,h)*1.0))
        self.is_scattered=False
        self.last_w = w
        self.last_h = h

    def pick_new_target_outside_box(self):
        w = max(20, self.last_w)
        h = max(20, self.last_h)
        radius = max(12, self.size_outside // 2)
        gap = max(6, int(min(w,h)*0.12))
        margin = int(max(gap + radius, min(w,h)*0.35))
        side = random.choice(['top','bottom','left','right'])
        jitter=random.uniform(-0.35,0.35)
        if side=='top':
            self.target_dx=int(jitter*w)
            self.target_dy=-(h//2+margin)
        elif side=='bottom':
            self.target_dx=int(jitter*w)
            self.target_dy=(h//2+margin)
        elif side=='left':
            self.target_dx=-(w//2+margin)
            self.target_dy=int(jitter*h)
        else:
            self.target_dx=(w//2+margin)
            self.target_dy=int(jitter*h)

    def update(self,x=None,y=None,w=None,h=None,scatter=False):
        self.phase+=self.float_speed
        if x is not None and y is not None and w is not None and h is not None:
            self.anchor_x = x + w//2
            self.anchor_y = y + h//2
            face_min = max(20, int(min(w,h)))
            self.size_inside = max(48, int(face_min * 0.95))
            self.size_outside = max(30, int(self.size_inside * 0.62))
            self.last_w = w
            self.last_h = h
            self.scatter_radius_max = max(60, int(min(w,h)*1.0))
        float_x=int(2*math.sin(self.phase))
        float_y=int(1*math.sin(self.phase/2))
        if scatter:
            self.base_size=self.size_outside
            if not self.is_scattered or (self.target_dx==0 and self.target_dy==0):
                self.pick_new_target_outside_box()
                self.is_scattered=True
            tgt_x=self.anchor_x+self.target_dx
            tgt_y=self.anchor_y+self.target_dy
            self.x=tgt_x+float_x*0.12
            self.y=tgt_y+float_y*0.12
            half_w=self.last_w/2
            half_h=self.last_h/2
            dx_from_anchor=self.x-self.anchor_x
            dy_from_anchor=self.y-self.anchor_y
            if abs(dx_from_anchor)<half_w and abs(dy_from_anchor)<half_h:
                if abs(dx_from_anchor)>=abs(dy_from_anchor):
                    push=(half_w+max(8,self.base_size//2))*(1 if dx_from_anchor>=0 else -1)
                    self.x=self.anchor_x+push
                else:
                    push=(half_h+max(8,self.base_size//2))*(1 if dy_from_anchor>=0 else -1)
                    self.y=self.anchor_y+push
        else:
            self.base_size=self.size_inside
            tgt_x=self.anchor_x+int(6*math.sin(self.phase))
            tgt_y=self.anchor_y+int(4*math.sin(self.phase/2))
            ease=0.25
            self.x=self.x*(1-ease)+tgt_x*ease
            self.y=self.y*(1-ease)+tgt_y*ease
            self.is_scattered=False
