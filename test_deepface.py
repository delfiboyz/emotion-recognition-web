# ultra_emoji_with_scatter.py
from deepface import DeepFace
import cv2
import time
import numpy as np
import math
import random

# ---------- Config ----------
WINDOW_TITLE = "Ultra Emoji + Emotion Scores (Vector)"
WINDOW_SIZE = (1280, 720)
BAR_WIDTH = 180
BAR_MAX_PIXELS = 160
SMOOTHING_ALPHA = 0.35
EMOJI_MODES = ["vector", "cartoon", "neon"]
EMOJI_MODE_IDX = 2  # default neon

EMOJI_PARTICLE_COLOR = {
    "happy": (0, 255, 255),
    "sad": (255, 0, 0),
    "angry": (0, 0, 255),
    "surprise": (255, 255, 255),
    "neutral": (0, 255, 0),
    "disgust": (0, 128, 0),
    "fear": (128, 0, 128)
}
EMOTIONS_ORDER = ["happy", "sad", "angry", "surprise", "neutral", "disgust", "fear"]

# ---------------- Super Emoji Renderer ----------------
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
        else:
            self._draw_neon(frame, center, size, emotion, frame_idx)

    # Vector flat emoji
    def _draw_vector(self, frame, center, size, emotion):
        color = self.colors.get(emotion, (255,255,0))
        radius = size//2
        cv2.circle(frame, center, radius, color, -1)
        # eyes
        ex, ey = radius//2, radius//3
        cv2.circle(frame, (center[0]-ex, center[1]-ey), radius//6, (0,0,0), -1)
        cv2.circle(frame, (center[0]+ex, center[1]-ey), radius//6, (0,0,0), -1)
        # mouth
        mouth_y = center[1]+radius//3
        if emotion=="happy": cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//4),0,0,180,(0,0,0),2)
        elif emotion=="sad": cv2.ellipse(frame,(center[0],mouth_y+radius//6),(radius//2,radius//4),0,180,360,(0,0,0),2)
        elif emotion=="angry": cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)
        elif emotion=="surprise": cv2.circle(frame,(center[0],mouth_y),radius//4,(0,0,0),2)
        else: cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)

    # Cartoon emoji
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
        if emotion=="happy": cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//4),0,0,180,(0,0,0),2)
        elif emotion=="sad": cv2.ellipse(frame,(center[0],mouth_y+radius//6),(radius//2,radius//4),0,180,360,(0,0,0),2)
        elif emotion=="angry": cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),3)
        elif emotion=="surprise": cv2.circle(frame,(center[0],mouth_y),radius//5,(0,0,0),2)
        else: cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)

    # Neon glow emoji
    def _draw_neon(self, frame, center, size, emotion, frame_idx):
        radius = size//2
        color = self.colors.get(emotion,(255,255,0))
        # glow
        for r in range(radius,radius+15,3):
            overlay=frame.copy()
            cv2.circle(overlay,center,r,color,2)
            cv2.addWeighted(overlay,0.05,frame,0.95,0,frame)
        cv2.circle(frame,center,radius,color,-1)
        ex, ey = radius//2,radius//3
        pupil_jitter = int(2*math.sin(frame_idx/5))
        cv2.circle(frame,(center[0]-ex,center[1]-ey),radius//6,(0,0,0),-1)
        cv2.circle(frame,(center[0]+ex,center[1]-ey),radius//6,(0,0,0),-1)
        cv2.circle(frame,(center[0]-ex+pupil_jitter,center[1]-ey),radius//12,(255,255,255),-1)
        cv2.circle(frame,(center[0]+ex+pupil_jitter,center[1]-ey),radius//12,(255,255,255),-1)
        mouth_y=center[1]+radius//3
        if emotion=="happy": cv2.ellipse(frame,(center[0],mouth_y),(radius//2,radius//3),0,0,180,(0,0,0),3)
        elif emotion=="sad": cv2.ellipse(frame,(center[0],mouth_y+radius//5),(radius//2,radius//3),0,180,360,(0,0,0),3)
        elif emotion=="angry": cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),3)
        elif emotion=="surprise": cv2.circle(frame,(center[0],mouth_y),radius//4,(0,0,0),3)
        else: cv2.line(frame,(center[0]-radius//2,mouth_y),(center[0]+radius//2,mouth_y),(0,0,0),2)
        # shimmer particles
        for i in range(12):
            angle=(i*30+frame_idx*5)%360
            rad=math.radians(angle)
            px=int(center[0]+(radius+10)*math.cos(rad))
            py=int(center[1]+(radius+10)*math.sin(rad))
            cv2.circle(frame,(px,py),3,color,-1)

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

# ---------------- EMA smoothing ----------------
def smooth_scores(prev_scores,new_scores,alpha=SMOOTHING_ALPHA):
    if prev_scores is None:
        return {k: float(v) for k,v in new_scores.items()}
    out={}
    for k in set(list(prev_scores.keys())+list(new_scores.keys())):
        p=float(prev_scores.get(k,0.0))
        n=float(new_scores.get(k,0.0))
        out[k]=p*(1-alpha)+n*alpha
    return out

# ---------------- Main ----------------
def analyze_with_bars_vector():
    cap=cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera"); return

    cv2.namedWindow(WINDOW_TITLE,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_TITLE,WINDOW_SIZE[0],WINDOW_SIZE[1])

    frame_idx=0
    fps_start=time.time()
    emojis=[]
    smoothed_scores=[]
    renderer=SuperEmojiRenderer(mode=EMOJI_MODES[EMOJI_MODE_IDX])

    scatter_mode=False  # toggled by user: if True emojis move away from face

    while True:
        ret,frame=cap.read()
        if not ret: break
        frame_idx+=1
        fh,fw=frame.shape[:2]

        try:
            results=DeepFace.analyze(frame,actions=['emotion'],enforce_detection=False)
            if not isinstance(results,list): results=[results]
            if len(results)==0:
                emojis=[]
                smoothed_scores=[]
            else:
                if len(emojis)!=len(results):
                    # re-create emoji objects if face count changed
                    emojis=[]
                    smoothed_scores=[]
                    for r in results:
                        emojis.append(UltraEmoji(r['dominant_emotion'],r['region']['x'],r['region']['y'],r['region']['w'],r['region']['h']))
                        smoothed_scores.append(None)

                for idx,r in enumerate(results):
                    x=int(r['region']['x']); y=int(r['region']['y'])
                    ww=int(r['region']['w']); hh=int(r['region']['h'])
                    dominant=r['dominant_emotion']
                    raw_scores=r.get('emotion',{})

                    # update emoji data
                    emojis[idx].update(x,y,ww,hh,scatter=scatter_mode)
                    emojis[idx].emotion=dominant

                    # face box and label
                    cv2.rectangle(frame,(x,y),(x+ww,y+hh),(0,255,255),2)
                    label_color=EMOJI_PARTICLE_COLOR.get(dominant,(0,255,255))
                    cv2.putText(frame,f"EMOTION: {dominant.upper()}",(x,max(y-12,16)),cv2.FONT_HERSHEY_SIMPLEX,0.75,label_color,2)

                    # bars
                    smoothed_scores[idx]=smooth_scores(smoothed_scores[idx],raw_scores)
                    bar_x0=min(fw-BAR_WIDTH-12,x+ww+12)
                    bar_y0=y
                    cv2.rectangle(frame,(bar_x0-6,bar_y0-6),(bar_x0+BAR_WIDTH+6,bar_y0+len(EMOTIONS_ORDER)*24+6),(10,10,10),-1)
                    for i,emo in enumerate(EMOTIONS_ORDER):
                        val=int(smoothed_scores[idx].get(emo,0.0) if smoothed_scores[idx] is not None else 0)
                        val=max(0,min(100,int(round(val))))
                        length=int(BAR_MAX_PIXELS*(val/100.0))
                        y_line=bar_y0+i*24
                        cv2.putText(frame,emo[:6].upper(),(bar_x0,y_line+16),cv2.FONT_HERSHEY_SIMPLEX,0.5,(200,200,200),1)
                        cv2.rectangle(frame,(bar_x0+62,y_line+4),(bar_x0+62+BAR_MAX_PIXELS,y_line+20),(50,50,50),-1)
                        color=EMOJI_PARTICLE_COLOR.get(emo,(200,200,0))
                        cv2.rectangle(frame,(bar_x0+62,y_line+4),(bar_x0+62+length,y_line+20),color,-1)
                        cv2.putText(frame,f"{val:3d}%",(bar_x0+62+BAR_MAX_PIXELS+6,y_line+16),cv2.FONT_HERSHEY_SIMPLEX,0.45,(220,220,220),1)
        except Exception:
            emojis=[]
            smoothed_scores=[]
            pass

        # draw emojis (they manage their own positions)
        for e in emojis:
            renderer.draw(frame,(int(e.x),int(e.y)),int(e.base_size),e.emotion,frame_idx)

        # HUD: FPS and mode
        fps=frame_idx/(time.time()-fps_start+1e-6)
        cv2.putText(frame,f"FPS: {fps:.2f}",(12,34),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2)
        mode_text = f"Mode: {renderer.mode.upper()} | Scatter: {'ON' if scatter_mode else 'OFF'}"
        cv2.putText(frame,mode_text,(12,64),cv2.FONT_HERSHEY_SIMPLEX,0.7,(200,200,200),2)
        cv2.putText(frame,"Controls: q=quit 1/2/3=mode e=toggle scatter",(12,fw-40),cv2.FONT_HERSHEY_SIMPLEX,0.5,(180,180,180),1)

        cv2.imshow(WINDOW_TITLE,frame)
        key=cv2.waitKey(1)
        if key & 0xFF==ord('q'): break
        elif key & 0xFF==ord('1'): renderer.set_mode("vector")
        elif key & 0xFF==ord('2'): renderer.set_mode("cartoon")
        elif key & 0xFF==ord('3'): renderer.set_mode("neon")
        elif key & 0xFF==ord('e'):
            # toggle scatter on/off
            scatter_mode = not scatter_mode
            # when turning scatter on, ensure each emoji has a target
            if scatter_mode:
                for em in emojis:
                    em.pick_new_target_outside_box()

    cap.release()
    cv2.destroyAllWindows()

if __name__=="__main__":
    analyze_with_bars_vector()
