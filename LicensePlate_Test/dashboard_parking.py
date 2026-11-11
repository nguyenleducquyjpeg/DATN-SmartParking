import argparse
import queue
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from employee_registry import Registry, EmployeePanel, normalize_plate

BASE = Path(__file__).resolve().parent
ENTRY_SNAPSHOT_DIR = BASE / 'parking_snapshots' / 'entry'
CAM_DISPLAY_W, CAM_DISPLAY_H = 520, 320
db = None


def initialize_runtime():
    global cv2, Image, ImageTk, db
    import cv2
    from PIL import Image, ImageTk
    import firebase_admin
    from firebase_admin import credentials, db
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(BASE / 'firebase_key.json')),
            {'databaseURL':'https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app',
             'httpTimeout':10})


# =========================================================
# GIAO DIỆN CHUẨN ĐẦY ĐỦ CÂN ĐỐI 4 Ô (CĂN GIỮA)
# =========================================================
class VASSProParking:
    def __init__(self, root, demo=False):
        self.root = root
        self.demo = demo
        self.closing = False
        self.camera_queue = queue.Queue(maxsize=8)
        self.db_results = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending_publish = set()
        self.workers = {}
        self.generation = {'IN':0,'OUT':0}
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.title("Logistics - Kiểm soát xe nhân viên")
        self.root.geometry("1500x940")
        self.root.minsize(1150,800)
        self.root.configure(bg="#d9d9d9")

        top_bar = tk.Label(root, text="LOGISTICS — KIỂM SOÁT NHÂN VIÊN, XE ĐĂNG KÝ VÀ NỒNG ĐỘ CỒN", font=("Arial", 14, "bold"), bg="#002060", fg="white", anchor="w", padx=10, pady=8)
        top_bar.pack(fill=tk.X)

        main_container = tk.Frame(root, bg="#d9d9d9")
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # =========================================================
        # BÊN TRÁI: BẢNG THÔNG TIN VÀ ĐIỀU KHIỂN
        # =========================================================
        left_shell = tk.Frame(main_container, bg="white", width=425)
        left_shell.pack(side=tk.LEFT, fill=tk.Y, padx=3)
        left_shell.pack_propagate(False)
        canvas = tk.Canvas(left_shell, bg='white', highlightthickness=0)
        scrollbar = tk.Scrollbar(left_shell, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_panel = tk.Frame(canvas, bg='white')
        window = canvas.create_window((0,0),window=left_panel,anchor='nw')
        left_panel.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))

        self.banner_lbl = tk.Label(left_panel, text="MÔ PHỎNG GIAO DIỆN" if demo else "MỞ CAMERA VÀ QUÉT THẺ NHÂN VIÊN", font=("Arial", 10, "bold"), bg="#163b60", fg="white", pady=6, wraplength=380)
        self.banner_lbl.pack(fill=tk.X, padx=5, pady=5)

        # Biển số Vào & Ô nhập thủ công Lối Vào
        tk.Label(left_panel, text="BIỂN SỐ VÀO", font=("Arial", 9, "bold"), bg="white", fg="gray").pack(anchor="w", padx=10)
        self.lbl_plate_in = tk.Label(left_panel, text="---", font=("Arial", 16, "bold"), bg="#e6f2ff", fg="#002060", relief=tk.SUNKEN, bd=2)
        self.lbl_plate_in.pack(fill=tk.X, padx=10, pady=2)

        manual_in_frame = tk.Frame(left_panel, bg="white")
        manual_in_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(manual_in_frame, text="Nhập vào (Enter):", font=("Arial", 9, "bold"), bg="white").pack(side=tk.LEFT)
        
        self.plate_manual_in_var = tk.StringVar()
        self.entry_manual_in = tk.Entry(manual_in_frame, textvariable=self.plate_manual_in_var, font=("Arial", 11, "bold"), fg="#002060")
        self.entry_manual_in.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_manual_in.bind("<Return>", self.submit_manual_in)

        # Biển số Ra & Ô nhập thủ công Lối Ra
        tk.Label(left_panel, text="BIỂN SỐ RA", font=("Arial", 9, "bold"), bg="white", fg="gray").pack(anchor="w", padx=10, pady=(5,0))
        self.lbl_plate_out = tk.Label(left_panel, text="---", font=("Arial", 16, "bold"), bg="#ffe6e6", fg="red", relief=tk.SUNKEN, bd=2)
        self.lbl_plate_out.pack(fill=tk.X, padx=10, pady=2)

        manual_frame = tk.Frame(left_panel, bg="white")
        manual_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(manual_frame, text="Nhập ra (Enter):", font=("Arial", 9, "bold"), bg="white").pack(side=tk.LEFT)
        
        self.plate_manual_var = tk.StringVar()
        self.entry_manual = tk.Entry(manual_frame, textvariable=self.plate_manual_var, font=("Arial", 11, "bold"), fg="red")
        self.entry_manual.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_manual.bind("<Return>", self.submit_manual)

        # =========================================================
        # BÊN PHẢI: 4 KHUNG CAMERA
        # =========================================================
        right_panel = tk.Frame(main_container, bg="#d9d9d9")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=3)

        right_panel.grid_columnconfigure(0, weight=1, uniform="rcol")
        right_panel.grid_columnconfigure(1, weight=1, uniform="rcol")
        right_panel.grid_rowconfigure(0, weight=1, uniform="rrow")
        right_panel.grid_rowconfigure(1, weight=1, uniform="rrow")

        # --- Ô 1 (Trên Trái): CAMERA VÀO (LIVE) ---
        f_cam1 = tk.LabelFrame(right_panel, text=" 1. CAMERA HÌNH ẢNH VÀO (LIVE) ", font=("Arial", 9, "bold"), bg="white")
        f_cam1.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        ctrl1 = tk.Frame(f_cam1, bg="#eee", height=25)
        ctrl1.pack(fill=tk.X)
        tk.Label(ctrl1, text="Index:", font=("Arial", 8), bg="#eee").pack(side=tk.LEFT, padx=2)
        self.idx_in = tk.StringVar(value="0")
        tk.Entry(ctrl1, textvariable=self.idx_in, width=3).pack(side=tk.LEFT)
        tk.Button(ctrl1, text="Mở Cam", bg="green", fg="white", font=("Arial", 8, "bold"), command=self.start_cam_in).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl1, text="Tắt", bg="red", fg="white", font=("Arial", 8, "bold"), command=self.stop_cam_in).pack(side=tk.LEFT)

        self.lbl_cam_in = tk.Label(f_cam1, bg="black", width=1, height=1, anchor=tk.CENTER)
        self.lbl_cam_in.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.lbl_cam_in.pack_propagate(False)

        # --- Ô 2 (Trên Phải): CAMERA RA (LIVE) ---
        f_cam2 = tk.LabelFrame(right_panel, text=" 2. CAMERA HÌNH ẢNH RA (LIVE) ", font=("Arial", 9, "bold"), bg="white")
        f_cam2.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        
        ctrl2 = tk.Frame(f_cam2, bg="#eee", height=25)
        ctrl2.pack(fill=tk.X)
        tk.Label(ctrl2, text="Index:", font=("Arial", 8), bg="#eee").pack(side=tk.LEFT, padx=2)
        self.idx_out = tk.StringVar(value="1")
        tk.Entry(ctrl2, textvariable=self.idx_out, width=3).pack(side=tk.LEFT)
        tk.Button(ctrl2, text="Mở Cam", bg="green", fg="white", font=("Arial", 8, "bold"), command=self.start_cam_out).pack(side=tk.LEFT, padx=2)
        tk.Button(ctrl2, text="Tắt", bg="red", fg="white", font=("Arial", 8, "bold"), command=self.stop_cam_out).pack(side=tk.LEFT)

        self.lbl_cam_out = tk.Label(f_cam2, bg="black", width=1, height=1, anchor=tk.CENTER)
        self.lbl_cam_out.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.lbl_cam_out.pack_propagate(False)

        # --- Ô 3 (Dưới Trái): ẢNH XE VÀO (SNAPSHOT) ---
        f_cam3 = tk.LabelFrame(right_panel, text=" 3. ẢNH XE VÀO (SNAPSHOT) ", font=("Arial", 9, "bold"), bg="white")
        f_cam3.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.lbl_snapshot_in = tk.Label(f_cam3, text="Chưa có ảnh xe vào", fg="gray", bg="#111", width=1, height=1, anchor=tk.CENTER)
        self.lbl_snapshot_in.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.lbl_snapshot_in.pack_propagate(False)

        # --- Ô 4 (Dưới Phải): ẢNH XE RA (SNAPSHOT) ---
        f_cam4 = tk.LabelFrame(right_panel, text=" 4. ẢNH XE RA (SNAPSHOT) ", font=("Arial", 9, "bold"), bg="white")
        f_cam4.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        self.lbl_snapshot_out = tk.Label(f_cam4, text="Chưa có ảnh xe ra", fg="gray", bg="#111", width=1, height=1, anchor=tk.CENTER)
        self.lbl_snapshot_out.pack(padx=5, pady=5, expand=True, fill=tk.BOTH)
        self.lbl_snapshot_out.pack_propagate(False)

        # Khởi tạo biến camera
        self.cap_in = None
        self.cap_out = None

        self.last_yolo_in = 0
        self.last_ocr_in = 0
        self.candidate_in = ""
        self.stable_in = 0
        self.current_plate_in = ""
        self.saved_plate_in = ""

        self.last_yolo_out = 0
        self.last_ocr_out = 0
        self.candidate_out = ""
        self.stable_out = 0
        self.current_plate_out = ""
        self.saved_plate_out = ""

        self.employee_panel = EmployeePanel(self, None if demo else db, left_panel)
        self.registry = self.employee_panel.registry
        self.last_publish = {"IN": 0, "OUT": 0}
        if demo:
            tk.Button(left_panel,text='Nạp tình huống minh họa',command=self.demo_scenario).pack(fill='x',padx=10,pady=5)
        self.update_loop()

    def start_camera(self, lane):
        if self.demo:
            messagebox.showinfo('Mô phỏng','Chế độ xem giao diện không dùng camera hoặc Firebase.')
            return
        try:
            idx=int((self.idx_in if lane=='IN' else self.idx_out).get())
            if lane in self.workers and self.workers[lane][2].is_alive():
                self.stop_camera(lane)
                self.banner_lbl.config(text=f'Đang dừng camera {lane}. Chờ xử lý xong rồi bấm Mở Cam lại.',bg='#163b60')
                return
            other='OUT' if lane=='IN' else 'IN'
            if other in self.workers and not self.workers[other][0].is_set() and self.workers[other][1]==idx:
                raise ValueError('Hai làn phải chọn hai camera khác nhau')
            self.stop_camera(lane)
            from gate_camera import run_camera
            stop=threading.Event()
            thread=threading.Thread(target=run_camera,args=(lane,idx,self.generation[lane],stop,self.camera_queue),daemon=True)
            self.workers[lane]=(stop,idx,thread)
            thread.start()
            self.banner_lbl.config(text=f'Đang mở camera {lane} và khởi tạo nhận diện...',bg='#163b60')
        except Exception as exc:messagebox.showerror('Camera',str(exc))

    def stop_camera(self,lane):
        if lane in self.workers:self.workers[lane][0].set()
        self.generation[lane]+=1
        label=self.lbl_cam_in if lane=='IN' else self.lbl_cam_out
        label.config(image='',text='Camera đã tắt',fg='white');label.imgtk=None
        self.employee_panel.observe(lane,'')

    def start_cam_in(self):self.start_camera('IN')
    def start_cam_out(self):self.start_camera('OUT')
    def stop_cam_in(self):self.stop_camera('IN')
    def stop_cam_out(self):self.stop_camera('OUT')

    def display_frame(self,label,frame):
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        width=max(100,label.winfo_width());height=max(80,label.winfo_height())
        img=Image.fromarray(rgb);img.thumbnail((width,height),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(img);label.imgtk=photo;label.configure(image=photo,text='')

    def update_loop(self):
        if self.closing:return
        latest={}
        while not self.camera_queue.empty():
            kind,lane,generation,payload=self.camera_queue.get_nowait()
            if generation==self.generation[lane]:latest[lane]=(kind,payload)
        for lane,(kind,payload) in latest.items():
            if kind=='error':
                self.banner_lbl.config(text=f'Camera {lane}: {payload}',bg='#b74732')
                if lane in self.workers:self.workers[lane][0].set()
                continue
            frame,plate=payload
            self.display_frame(self.lbl_cam_in if lane=='IN' else self.lbl_cam_out,frame)
            if plate:
                (self.lbl_plate_in if lane=='IN' else self.lbl_plate_out).config(text=plate)
                self.employee_panel.observe(lane,plate)
                if lane not in self.pending_publish and time.time()-self.last_publish[lane]>15:
                    if lane=='IN':self.save_snapshot_in(frame,plate)
                    else:self.save_snapshot_out(frame)
                    self.request_vehicle(plate,lane)
        while not self.db_results.empty():
            lane,ok,note,plate=self.db_results.get_nowait()
            self.pending_publish.discard(lane)
            self.banner_lbl.config(text=f'{lane}: {note}',bg='#163b60' if ok else '#b74732')
            if ok and lane=='OUT':self.show_entry_snapshot_for_plate(plate)
        self.loop_timer=self.root.after(50,self.update_loop)

    def request_vehicle(self,plate,lane,source='CAMERA'):
        try:plate=normalize_plate(plate)
        except ValueError as exc:
            self.banner_lbl.config(text=str(exc),bg='#b74732');return False
        self.employee_panel.observe(lane,plate,source)
        if self.demo:
            self.banner_lbl.config(text='Mô phỏng: chỉ cập nhật biển số đối chiếu, không gửi lệnh.',bg='#163b60');return False
        if lane in self.pending_publish:return False
        self.pending_publish.add(lane);self.last_publish[lane]=time.time()
        def task():
            try:
                self.publish_vehicle(plate,lane,source)
                self.db_results.put((lane,True,'Đã gửi biển số; chờ ESP32 đối chiếu thẻ',plate))
            except Exception as exc:self.db_results.put((lane,False,str(exc),plate))
        self.executor.submit(task)
        return True

    def demo_scenario(self):
        now=int(time.time()*1000)
        for lane,code,name,uid,plate in [('IN','DEMO01','Nhân viên minh họa 1','11223344','59X112345'),('OUT','DEMO02','Nhân viên minh họa 2','55667788','76G108216')]:
            person=dict(maNhanVien=code,hoTen=name,boPhan='Giao nhận',rfid=uid,bienSo=plate,hoatDong=True)
            sid=uuid.uuid4().hex
            state=self.employee_panel.lanes[lane]
            state.scan(dict(eventId=sid,rfid=uid,timestamp=now),person)
            state.observe(plate,'MANUAL')
            state.status(dict(scanId=sid,rfid=uid,sequence=1,timestamp=now,trangThai='OPENED' if lane=='IN' else 'FAIL',adc=250 if lane=='OUT' else None,nguongADC=200 if lane=='OUT' else None))
        self.employee_panel.render()

    def close(self):
        self.closing=True
        for stop,idx,thread in self.workers.values():stop.set()
        self.employee_panel.close()
        self.executor.shutdown(wait=False,cancel_futures=True)
        try:self.root.after_cancel(self.loop_timer)
        except (tk.TclError,AttributeError):pass
        self.root.destroy()

    def _display_snapshot_in(self, frame):
        """Hien thi mot frame da luu trong o anh xe vao."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb).resize((CAM_DISPLAY_W, CAM_DISPLAY_H), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(image=pil_img)
        self.lbl_snapshot_in.imgtk = tk_img
        self.lbl_snapshot_in.configure(image=tk_img, text="")

    def _entry_snapshot_path(self, plate):
        safe_plate = re.sub(r"[^A-Z0-9]", "", plate.upper())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return ENTRY_SNAPSHOT_DIR / f"{safe_plate}_{timestamp}.jpg"

    def save_snapshot_in(self, frame, plate=None):
        try:
            self._display_snapshot_in(frame)
            if plate:
                ENTRY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
                snapshot_path = self._entry_snapshot_path(plate)
                cv2.imwrite(str(snapshot_path), frame)
                print(f"Da luu anh xe vao [{plate}]: {snapshot_path}")
        except Exception as e:
            print("Snapshot In error:", e)

    def show_entry_snapshot_for_plate(self, plate):
        """Tai anh xe vao gan nhat theo bien so de doi chieu khi xe ra."""
        try:
            safe_plate = re.sub(r"[^A-Z0-9]", "", plate.upper())
            if not ENTRY_SNAPSHOT_DIR.exists():
                return False
            matches = sorted(
                ENTRY_SNAPSHOT_DIR.glob(f"{safe_plate}_*.jpg"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if not matches:
                return False
            frame = cv2.imread(str(matches[0]))
            if frame is None:
                return False
            self._display_snapshot_in(frame)
            print(f"Da tai anh xe vao de doi chieu [{plate}]: {matches[0]}")
            return True
        except Exception as e:
            print("Load entry snapshot error:", e)
            return False

    def save_snapshot_out(self, frame):
        try:
            self.last_out_frame = frame.copy()
            folder=BASE / "parking_snapshots" / "exit"
            folder.mkdir(parents=True,exist_ok=True)
            cv2.imwrite(str(folder / (uuid.uuid4().hex+".jpg")), self.last_out_frame)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb).resize((CAM_DISPLAY_W, CAM_DISPLAY_H), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(image=pil_img)
            self.lbl_snapshot_out.imgtk = tk_img
            self.lbl_snapshot_out.configure(image=tk_img, text="")
        except Exception as e:
            print("Snapshot Out error:", e)

    def publish_vehicle(self, plate, direction, source='CAMERA'):
        # Called by a background worker; never touches Tk widgets.
        plate=normalize_plate(plate)
        person=self.registry.by_plate(plate)
        if not person or person.get('hoatDong') is not True:
            raise ValueError('Xe chưa đăng ký hoặc hồ sơ đã ngừng hiệu lực')
        inside=db.reference('XeTrongBai/'+person['rfid']).get() is True
        if inside != (direction=='OUT'):
            raise ValueError('Xe không ở trong bãi' if direction=='OUT' else 'Xe đã ở trong bãi')
        data=dict(bienSo=plate,rfid=person['rfid'],maNhanVien=person['maNhanVien'],hoTen=person['hoTen'],
                  requestId=uuid.uuid4().hex,timestamp={'.sv':'timestamp'},nguon=source,
                  thoiGian=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),trangThai='WAITING_RFID')
        db.reference('XeDangVao' if direction=='IN' else 'XeDangRa').set(data)
        return True

    def process_in_db(self,plate):return self.request_vehicle(plate,'IN')
    def process_out_db(self,plate):return self.request_vehicle(plate,'OUT')

    def submit_manual_in(self,event):
        self.request_vehicle(self.plate_manual_in_var.get(),'IN','MANUAL')

    def submit_manual(self,event):
        self.request_vehicle(self.plate_manual_var.get(),'OUT','MANUAL')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Preview only; no Firebase, camera or hardware access')
    args=parser.parse_args()
    if not args.demo:initialize_runtime()
    root=tk.Tk();app=VASSProParking(root,demo=args.demo);root.mainloop()
