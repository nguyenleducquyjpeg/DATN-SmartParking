"""Optional camera adapter; reuses existing model weights, does not access cloud."""
import threading
import time
import uuid
from pathlib import Path
from core import plate_key

_lock = threading.Lock()
_model = _ocr = None


def capture_plate(index, base):
    global _model, _ocr
    import cv2
    from ultralytics import YOLO
    from paddleocr import PaddleOCR
    with _lock:
        weights = base.parent/'LicensePlate_Test/runs/detect/runs/plate_v1/weights/best.pt'
        if not weights.exists(): weights=base.parent/'LicensePlate_Test/best.pt'
        if _model is None:
            _model=YOLO(str(weights))
            _ocr=PaddleOCR(lang='en',device='cpu',enable_mkldnn=False,
                          use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,
                          text_detection_model_name='PP-OCRv5_mobile_det',text_recognition_model_name='PP-OCRv5_mobile_rec')
        cap=cv2.VideoCapture(index)
        try:
            if not cap.isOpened():raise ValueError('Không mở được camera')
            previous='';stable=0
            for attempt in range(24):
                ok,frame=cap.read()
                if not ok:continue
                detections=_model(frame,conf=.6,imgsz=960,device='cpu',verbose=False)
                boxes=[b for r in detections if r.boxes is not None for b in r.boxes]
                if not boxes:previous='';stable=0;continue
                b=max(boxes,key=lambda b:float(b.conf[0]))
                x1,y1,x2,y2=map(int,b.xyxy[0]);h,w=frame.shape[:2]
                crop=frame[max(0,y1-8):min(h,y2+8),max(0,x1-8):min(w,x2+8)]
                if not crop.size:continue
                results=_ocr.predict(cv2.resize(crop,None,fx=3,fy=3))
                parts=[]
                for result in results:
                    data=result.json;data=data.get('res',data)
                    parts.extend(t for t,s in zip(data.get('rec_texts',[]),data.get('rec_scores',[])) if float(s)>=.6)
                try:plate=plate_key(''.join(parts))
                except ValueError:previous='';stable=0;continue
                stable=stable+1 if plate==previous else 1;previous=plate
                if stable>=3:
                    folder=base/'data'/'snapshots';folder.mkdir(exist_ok=True)
                    path=folder/(uuid.uuid4().hex+'.jpg')
                    if not cv2.imwrite(str(path),frame):raise ValueError('Không lưu được ảnh camera')
                    return dict(plate=plate,path=str(path))
                time.sleep(.1)
            raise ValueError('Chưa nhận diện ổn định. Chỉnh camera hoặc nhập biển số có kiểm tra.')
        finally:cap.release()
