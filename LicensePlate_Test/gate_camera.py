"""Camera/inference workers. No Tk calls; model shared behind a lock."""
import queue
import threading
import time
from pathlib import Path
from employee_registry import normalize_plate

_lock=threading.Lock()
_model=_ocr=None


def recognize(frame):
    global _model,_ocr
    import cv2
    with _lock:
        if _model is None or _ocr is None:
            from ultralytics import YOLO
            from paddleocr import PaddleOCR
            base=Path(__file__).resolve().parent
            weights=base/'runs/detect/runs/plate_v1/weights/best.pt'
            if not weights.exists():weights=base/'best.pt'
            _model=YOLO(str(weights))
            _ocr=PaddleOCR(lang='en',device='cpu',enable_mkldnn=False,
                use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,
                text_detection_model_name='PP-OCRv5_mobile_det',text_recognition_model_name='PP-OCRv5_mobile_rec')
        # CPU works without assuming a CUDA device is present.
        results=_model(frame,conf=.6,imgsz=960,device='cpu',verbose=False)
        boxes=[b for r in results if r.boxes is not None for b in r.boxes]
        if not boxes:return ''
        best=max(boxes,key=lambda b:float(b.conf[0]))
        x1,y1,x2,y2=map(int,best.xyxy[0]);h,w=frame.shape[:2]
        crop=frame[max(0,y1-8):min(h,y2+8),max(0,x1-8):min(w,x2+8)]
        if not crop.size:return ''
        texts=[]
        for result in _ocr.predict(cv2.resize(crop,None,fx=3,fy=3)):
            data=result.json;data=data.get('res',data)
            texts.extend(t for t,s in zip(data.get('rec_texts',[]),data.get('rec_scores',[])) if float(s)>=.6)
        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,160,90),2)
        try:return normalize_plate(''.join(texts))
        except ValueError:return ''


def run_camera(lane,index,generation,stop,output):
    import cv2
    cap=None
    def emit(kind,payload):
        item=(kind,lane,generation,payload)
        try:output.put_nowait(item)
        except queue.Full:
            try:output.get_nowait()
            except queue.Empty:pass
            try:output.put_nowait(item)
            except queue.Full:pass
    try:
        cap=cv2.VideoCapture(index)
        if not cap.isOpened():raise RuntimeError(f'Không mở được camera {index}')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
        previous='';count=0;plate='';last_detection=0
        while not stop.is_set():
            ok,frame=cap.read()
            if not ok:raise RuntimeError('Không nhận được hình ảnh camera')
            now=time.monotonic()
            if now-last_detection>=.3:
                plate=recognize(frame);last_detection=time.monotonic()
                count=count+1 if plate and plate==previous else 1 if plate else 0
                previous=plate
            emit('frame',(frame,plate if count>=3 else ''))
            stop.wait(.04)
    except Exception as exc:emit('error',str(exc))
    finally:
        if cap is not None:cap.release()
