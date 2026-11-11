"""Firebase employee lookup and gate display; no network access on import."""
import queue
import re
import threading
from datetime import datetime
import tkinter as tk


def normalize_plate(value):
    value = re.sub(r'[\s.\-]', '', value.upper())
    if not re.fullmatch(r'[0-9]{2}[A-Z][A-Z0-9]{1,2}[0-9]{4,5}', value):
        raise ValueError('Biển số không hợp lệ; ví dụ 76-G1 082.16')
    return value


class Registry:
    def __init__(self, db):
        self.db = db

    def by_uid(self, uid):
        code = self.db.reference('HoSoNhanVien/theRFID/'+uid).get()
        return self.db.reference('HoSoNhanVien/nhanVien/'+code).get() if code else None

    def by_plate(self, plate):
        plate = normalize_plate(plate)
        code = self.db.reference('HoSoNhanVien/bienSo/'+plate).get()
        return self.db.reference('HoSoNhanVien/nhanVien/'+code).get() if code else None

class EmployeePanel:
    def __init__(self, dashboard, db, parent):
        from gate_session import LaneState
        self.dashboard, self.db = dashboard, db
        self.registry = Registry(db) if db else None
        self.queue = queue.Queue()
        self.seen = {}
        self.stopped = threading.Event()
        self.lanes = {lane: LaneState(lane) for lane in ('IN', 'OUT')}
        self.labels = {}
        self.status = tk.StringVar(value='MÔ PHỎNG — không kết nối Firebase' if not db else 'Đang kết nối dữ liệu cổng...')
        tk.Label(parent, textvariable=self.status, bg='white', fg='#52657d', wraplength=375,
                 anchor='w', font=('Segoe UI',9)).pack(fill='x', padx=10, pady=5)
        for lane, name in [('IN','LỐI VÀO'),('OUT','LỐI RA · KIỂM TRA CỒN')]:
            box = tk.LabelFrame(parent, text=' '+name+' ', bg='white', fg='#163b60',
                                font=('Segoe UI',10,'bold'), padx=7,pady=5)
            box.pack(fill='x',padx=10,pady=5)
            self.labels[lane] = {}
            for key in ('employee','department','card','registered','observed','comparison','test','state','detail'):
                label=tk.Label(box, text='', anchor='w',justify='left',bg='white',
                               fg='#243c55',font=('Segoe UI',9),wraplength=365)
                label.pack(fill='x',pady=1)
                self.labels[lane][key]=label
        tk.Label(parent,text='Trạng thái mở/đóng là phản hồi lệnh ESP32, chưa phải xác nhận xe đã qua.',
                 bg='white',fg='#64748b',wraplength=375,font=('Segoe UI',8),justify='left').pack(fill='x',padx=10,pady=4)
        if db: threading.Thread(target=self.poll,daemon=True).start()
        self.timer=dashboard.root.after(200,self.drain)
        self.render()

    def close(self):
        self.stopped.set()
        try:self.dashboard.root.after_cancel(self.timer)
        except tk.TclError:pass

    def poll(self):
        import time
        while not self.stopped.is_set():
            try:
                scans=self.db.reference('SuKienRFID').get() or {}
                for lane in ('IN','OUT'):
                    event=scans.get(lane)
                    if not isinstance(event,dict):continue
                    marker=event.get('eventId')
                    if not marker or marker==self.seen.get(lane):continue
                    if abs(time.time()*1000-event.get('timestamp',0))>90000:continue
                    person=self.registry.by_uid(event['rfid'])
                    self.queue.put(('scan',(lane,event,person)))
                    self.seen[lane]=marker
                statuses=self.db.reference('TrangThaiCong').get() or {}
                for lane in ('IN','OUT'):
                    if isinstance(statuses.get(lane),dict):self.queue.put(('status',(lane,statuses[lane])))
                self.queue.put(('connection',time.time()))
            except Exception as exc:self.queue.put(('error',str(exc)))
            self.stopped.wait(1)

    def observe(self,lane,plate,source='CAMERA'):
        self.lanes[lane].observe(plate,source)
        self.render()

    def render(self):
        from gate_session import REASONS
        for lane,s in self.lanes.items():
            p=s.person; labels=self.labels[lane]
            stamp=datetime.fromtimestamp(s.scan_at/1000).strftime('%H:%M:%S') if s.scan_at else '—'
            values={
                'employee':f"NV: {p.get('maNhanVien','—')} · {p.get('hoTen','Chờ quét thẻ') if not s.uid or p else 'Thẻ chưa đăng ký'}",
                'department':f"Bộ phận: {p.get('boPhan','—')} | Hiệu lực: {'Có' if p.get('hoatDong') is True else 'Không' if p else '—'}",
                'card':f"UID: {s.uid or '—'} | Quét lúc: {stamp}",
                'registered':f"Xe đăng ký: {p.get('bienSo','—')}",
                'observed':f"Biển đối chiếu: {s.plate or '—'} ({'nhập tay' if s.source=='MANUAL' else 'camera'})",
                'comparison':s.comparison(),
                'test':('Không yêu cầu đo cồn khi vào' if lane=='IN' else f"ADC: {s.adc if s.adc is not None else '—'} | Ngưỡng: {s.threshold if s.threshold is not None else '—'}"),
                'state':s.display_state(),
                'detail':REASONS.get(s.reason,s.reason) or ('Mã phiên: '+s.scan_id[-12:] if s.scan_id else 'Đưa xe vào vùng camera và quét thẻ nhân viên')}
            for key,value in values.items():labels[key].config(text=value)
            color='#b74732' if s.state in ('FAIL','ERROR','DENIED') else '#08776a' if s.state in ('PASS','OPENED','CLOSED') else '#163b60'
            labels['state'].config(fg=color,font=('Segoe UI',9,'bold'))
            labels['comparison'].config(fg='#b74732' if 'KHÔNG KHỚP' in s.comparison() else '#08776a')

    def drain(self):
        if self.stopped.is_set():return
        while not self.queue.empty():
            kind,data=self.queue.get_nowait()
            if kind=='scan':
                lane,event,person=data
                self.lanes[lane].scan(event,person)
            elif kind=='status':
                lane,event=data
                self.lanes[lane].status(event)
            elif kind=='connection':self.status.set('Đọc Firebase thành công lúc '+datetime.fromtimestamp(data).strftime('%H:%M:%S')+' · không phải tín hiệu sống ESP32')
            elif kind=='error':self.status.set('Mất kết nối dữ liệu: '+data)
        self.render()
        self.timer=self.dashboard.root.after(200,self.drain)
