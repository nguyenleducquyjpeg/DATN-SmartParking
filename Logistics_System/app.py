"""Run: python app.py --demo (no external packages required)."""
import argparse
import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import Store

BASE = Path(__file__).resolve().parent
LABELS = {'AUTHORIZED':'Được phép mở', 'WAIT_TEST':'Chờ đo', 'FAIL':'Không đạt',
          'ERROR':'Lỗi đo', 'EXPIRED':'Hết hạn', 'COMPLETED':'Đã qua cổng', 'CANCELLED':'Đã hủy'}


class App:
    def __init__(self, root, demo):
        self.root, self.demo = root, demo
        (BASE/'data').mkdir(exist_ok=True)
        self.store = Store(BASE/'data'/('demo.sqlite3' if demo else 'logistics.sqlite3'))
        # Restart never restores a previous permission to open the gate.
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET state='CANCELLED' WHERE state IN ('WAIT_TEST','AUTHORIZED')")
        self.serial = None
        self.scan = None
        self.sid = None
        self.capture = None
        self.messages = queue.Queue()
        root.title('Logistics • Nhân viên – Xe cá nhân – Kiểm tra cồn' + (' [MÔ PHỎNG]' if demo else ' [THIẾT BỊ]'))
        root.geometry('1240x800')
        root.minsize(1000, 700)
        ttk.Label(root, text='BƯU CỤC LOGISTICS • KIỂM SOÁT XE NHÂN VIÊN', font=('Segoe UI',18,'bold')).pack(pady=12)
        ttk.Label(root, text='Một nhân viên · Một xe máy đăng ký · Một thẻ RFID hiệu lực | '+
                  ('MÔ PHỎNG — dữ liệu riêng, không điều khiển phần cứng' if demo else 'CỔNG THIẾT BỊ — kết nối ESP32 qua USB')).pack()
        self.status = tk.StringVar(value='Sẵn sàng. Đăng ký nhân viên trước khi thực hiện lượt vào/ra.')
        ttk.Label(root, textvariable=self.status, wraplength=1180, foreground='#064f7c').pack(fill='x',padx=20,pady=10)
        tabs = ttk.Notebook(root)
        tabs.pack(fill='both', expand=True, padx=16,pady=8)
        self.people = ttk.Frame(tabs,padding=12)
        self.gate = ttk.Frame(tabs,padding=12)
        self.history = ttk.Frame(tabs,padding=12)
        tabs.add(self.people,text='Nhân viên & xe'); tabs.add(self.gate,text='Kiểm soát vào / ra'); tabs.add(self.history,text='Nhật ký & thống kê')
        self.build_people(); self.build_gate(); self.build_history()
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100,self.poll)

    def guarded(self, fn):
        try: fn()
        except Exception as exc:
            self.status.set(str(exc)); messagebox.showerror('Không thực hiện được', str(exc))
        finally: self.refresh()

    def field(self, parent, label, default='', width=24):
        box = ttk.Frame(parent); box.pack(side='left',padx=5,pady=6)
        ttk.Label(box,text=label).pack(anchor='w')
        var = tk.StringVar(value=default)
        ttk.Entry(box,textvariable=var,width=width).pack()
        return var

    def table(self, parent, columns, height=14):
        frame = ttk.Frame(parent); frame.pack(fill='both',expand=True,pady=8)
        tree = ttk.Treeview(frame,columns=columns,show='headings',height=height)
        for col in columns: tree.heading(col,text=col); tree.column(col,width=120)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y'); tree.pack(fill='both',expand=True)
        return tree

    def build_people(self):
        row=ttk.Frame(self.people);row.pack(fill='x')
        self.fields=[self.field(row,l,width=w) for l,w in [('Mã nhân viên',12),('Họ tên',24),('Bộ phận',18),('Biển số đăng ký',18),('UID thẻ RFID',22)]]
        actions=ttk.Frame(self.people);actions.pack(fill='x')
        ttk.Button(actions,text='Lưu hồ sơ',command=lambda:self.guarded(self.save_person)).pack(side='left',padx=5)
        ttk.Button(actions,text='Ngừng / khôi phục hiệu lực',command=lambda:self.guarded(self.toggle)).pack(side='left',padx=5)
        ttk.Button(actions,text='Xóa ô nhập',command=lambda:[v.set('') for v in self.fields]).pack(side='left',padx=5)
        ttk.Label(self.people,text='Chọn dòng để sửa. Mã nhân viên là định danh cố định; xe/thẻ không được trùng giữa các hồ sơ.').pack(anchor='w',pady=6)
        self.people_table=self.table(self.people,['Mã NV','Họ tên','Bộ phận','Biển số','RFID','Hiệu lực','Trong bãi'])
        self.people_table.bind('<<TreeviewSelect>>',self.select_person)

    def save_person(self):
        self.store.save_employee(*(v.get() for v in self.fields))
        self.status.set('Đã lưu hồ sơ nhân viên và xe đăng ký.')

    def select_person(self,_):
        selection=self.people_table.selection()
        if selection:
            values=self.people_table.item(selection[0],'values')
            for var,value in zip(self.fields,values):var.set(value)

    def toggle(self):
        employee=next((e for e in self.store.employees() if e['id']==self.fields[0].get().upper()),None)
        if not employee:raise ValueError('Chọn một nhân viên')
        self.store.set_active(employee['id'],not employee['active'])

    def build_gate(self):
        row=ttk.Frame(self.gate);row.pack(fill='x')
        self.port=self.field(row,'Cổng USB','COM3',12)
        ttk.Button(row,text='Kết nối ESP32',state='disabled' if self.demo else 'normal',command=lambda:self.guarded(self.connect)).pack(side='left',padx=8,pady=20)
        self.threshold=self.field(row,'Ngưỡng ADC thử nghiệm','200',22)
        ttk.Label(row,text='ADC thô, chưa quy đổi mg/L.\nĐạt khi 0 < ADC < ngưỡng.').pack(side='left',padx=12)
        row=ttk.Frame(self.gate);row.pack(fill='x')
        self.uid=self.field(row,'UID quét / nhập mô phỏng','',24)
        self.plate=self.field(row,'Biển số đối chiếu','',24)
        box=ttk.Frame(row);box.pack(side='left',padx=8)
        ttk.Label(box,text='Hướng').pack()
        self.direction=tk.StringVar(value='IN')
        ttk.Combobox(box,textvariable=self.direction,values=['IN','OUT'],state='readonly',width=8).pack()
        self.camera_index=self.field(row,'Camera index','0',12)
        ttk.Button(row,text='Chụp & đọc biển số',command=lambda:self.guarded(self.camera)).pack(side='left',padx=8,pady=20)
        self.observed=tk.BooleanVar(value=False)
        ttk.Checkbutton(self.gate,text='Bảo vệ đã đối chiếu người cầm thẻ với hồ sơ nhân viên và xác nhận biển số trên xe',variable=self.observed).pack(anchor='w',pady=8)
        ttk.Button(self.gate,text='1. Đối chiếu thẻ – nhân viên – xe',command=lambda:self.guarded(self.start)).pack(anchor='w',pady=6)
        self.person_label=tk.StringVar(value='Chưa có phiên kiểm tra')
        ttk.Label(self.gate,textvariable=self.person_label,font=('Segoe UI',12,'bold'),wraplength=1100).pack(anchor='w',pady=12)
        row=ttk.Frame(self.gate);row.pack(fill='x')
        self.adc=self.field(row,'ADC mô phỏng','100',16)
        self.ready=tk.BooleanVar(value=False)
        ttk.Checkbutton(row,text='Đã làm nóng cảm biến, kiểm tra thiết bị\nvà giám sát người thổi đúng quy trình',variable=self.ready).pack(side='left',padx=10)
        ttk.Button(row,text='2. Đo kiểm tra khi lấy xe ra',command=lambda:self.guarded(self.measure)).pack(side='left',padx=12)
        row=ttk.Frame(self.gate);row.pack(fill='x',pady=16)
        ttk.Button(row,text='3. Mở cổng theo kết quả',command=lambda:self.guarded(self.open_gate)).pack(side='left',padx=5)
        ttk.Button(row,text='4. Xác nhận xe đã đi qua',command=lambda:self.guarded(self.passage)).pack(side='left',padx=5)
        ttk.Label(self.gate,text='Lối vào: đối chiếu → mở → xác nhận xe qua. Lối ra: đối chiếu → đo → đạt → mở → xác nhận xe qua.\n'
                  'Không đạt/lỗi/hết hạn: quét và tạo phiên mới để kiểm tra lại. Mỗi lần đo được lưu riêng.\n'
                  'Nhập biển số thủ công được ghi nguồn MANUAL. Ảnh camera được lưu cục bộ khi nhận diện thành công.',wraplength=1100).pack(anchor='w',pady=12)

    def connect(self):
        import serial
        if self.serial:self.serial.close()
        self.serial=serial.Serial(self.port.get(),115200,timeout=0,write_timeout=1)
        self.serial_buffer=b''
        self.scan=None; self.sid=None
        self.status.set('Đã kết nối. Chờ ESP32 khởi động rồi quét thẻ tại đúng đầu đọc.')

    def send(self, obj):
        if not self.serial or not self.serial.is_open:raise ValueError('Chưa kết nối ESP32')
        self.serial.write((json.dumps(obj)+'\n').encode())

    def start(self):
        if not self.observed.get():raise ValueError('Cần bảo vệ đối chiếu người cầm thẻ và xe')
        if not self.demo:
            if not self.scan or time.monotonic()-self.scan['received']>80:raise ValueError('Quét lại thẻ trên ESP32')
            if self.uid.get()!=self.scan['uid'] or self.direction.get()!=self.scan['direction']:
                raise ValueError('UID/hướng phải khớp lần quét phần cứng mới nhất')
        source='DEMO' if self.demo else 'MANUAL'
        evidence=''
        if self.capture and self.capture['plate']==self.plate.get() and time.monotonic()-self.capture['at']<60:
            source='DEMO' if self.demo else 'CAMERA';evidence=self.capture['path']
        s=self.store.start(self.uid.get(),self.plate.get(),self.direction.get(),float(self.threshold.get()),source,evidence)
        self.sid=s['id']
        self.observed.set(False);self.ready.set(False)
        self.status.set('Đối chiếu thành công; tiếp tục theo trạng thái phiên.')

    def measure(self):
        s=self.store.session(self.sid)
        if s['state']!='WAIT_TEST':raise ValueError('Chỉ đo cho phiên lấy xe ra đang chờ đo')
        if not self.ready.get():raise ValueError('Xác nhận cảm biến sẵn sàng và giám sát lần thổi')
        self.ready.set(False)
        if self.demo:self.store.measure(self.sid,self.adc.get())
        else:self.send(dict(cmd='TEST',sid=self.sid,token=self.scan['token']))
        self.status.set('Đã ghi nhận lần đo.' if self.demo else 'Đang lấy mẫu cảm biến (3 giây)...')

    def open_gate(self):
        s=self.store.session(self.sid)
        if s['state']!='AUTHORIZED':raise ValueError('Chưa đủ điều kiện mở cổng')
        if s['gate_ack']:raise ValueError('Đã gửi mở cổng; xác nhận xe qua hoặc tạo phiên mới')
        if self.demo:self.store.acknowledge_gate(self.sid)
        else:self.send(dict(cmd='OPEN',sid=self.sid,token=self.scan['token']))
        self.status.set('Đã mô phỏng lệnh mở cổng.' if self.demo else 'Đã gửi lệnh, chờ ESP32 xác nhận.')

    def passage(self):
        self.store.confirm_passage(self.sid)
        self.status.set('Đã xác nhận xe qua cổng và cập nhật số xe trong bãi.')
        self.sid=None;self.scan=None;self.capture=None
        self.plate.set('');self.uid.set('')

    def camera(self):
        index=int(self.camera_index.get())
        self.status.set('Đang khởi tạo YOLO/OCR và chụp camera; lần đầu có thể mất thời gian...')
        def worker():
            try:
                from camera import capture_plate
                self.messages.put(('camera',capture_plate(index,BASE)))
            except Exception as exc:self.messages.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def build_history(self):
        row=ttk.Frame(self.history);row.pack(fill='x')
        self.search=self.field(row,'Mã NV / tên / biển số','',28)
        self.day=self.field(row,'Ngày YYYY-MM-DD (trống = tất cả)','',28)
        ttk.Button(row,text='Lọc / làm mới',command=self.refresh).pack(side='left',padx=10,pady=20)
        ttk.Button(row,text='Xuất CSV',command=lambda:self.guarded(self.export)).pack(side='left',padx=10)
        self.summary=tk.StringVar()
        ttk.Label(self.history,textvariable=self.summary,wraplength=1120).pack(anchor='w',pady=12)
        self.logs=self.table(self.history,['Thời gian','Mã NV','Họ tên','Biển số','Sự kiện','Chi tiết'])
        self.logs.column('Chi tiết',width=400)

    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='nhat_ky_logistics.csv')
        if path:self.store.export_csv(path,self.search.get(),self.day.get());self.status.set('Đã xuất nhật ký: '+path)

    def refresh(self):
        employees=self.store.employees()
        self.people_table.delete(*self.people_table.get_children())
        for e in employees:self.people_table.insert('', 'end',values=[e['id'],e['name'],e['department'],e['plate'],e['uid'],'Có' if e['active'] else 'Ngừng','Có' if e['inside'] else 'Không'])
        rows=self.store.events(self.search.get(),self.day.get())
        counts={k:sum(r['kind']==k for r in rows) for k in ['TEST_PASS','TEST_FAIL','TEST_ERROR','PASSAGE_IN','PASSAGE_OUT']}
        total=counts['TEST_PASS']+counts['TEST_FAIL']+counts['TEST_ERROR']
        self.summary.set(f"Toàn bưu cục: {len(employees)} nhân viên · {sum(e['inside'] for e in employees)} xe trong bãi | Bộ lọc: {total} lần đo · "
                         f"{counts['TEST_PASS']} đạt · {counts['TEST_FAIL']} không đạt · {counts['TEST_ERROR']} lỗi · {counts['PASSAGE_IN']} lượt vào · {counts['PASSAGE_OUT']} lượt ra")
        self.logs.delete(*self.logs.get_children())
        for r in rows[:500]:self.logs.insert('','end',values=[r['local_time'],r['employee_id'] or '',r['name'] or '',r['plate'] or '',r['kind'],r['detail']])
        if self.sid:
            s=self.store.session(self.sid)
            self.person_label.set(f"{s['employee_id']} · {s['name']} · {s['plate']} · {s['direction']} · {LABELS.get(s['state'],s['state'])} · ADC: {s['adc']} · ACK: {s['gate_ack']}")
        else:self.person_label.set('Chưa có phiên kiểm tra')

    def handle_device(self, msg):
        kind=msg.get('event')
        if kind=='CARD':
            # Invalidate previous UI grant immediately, including an unconfirmed gate opening.
            if self.sid:
                with self.store.db:self.store.db.execute("UPDATE sessions SET state='CANCELLED' WHERE id=? AND state IN ('WAIT_TEST','AUTHORIZED')",(self.sid,))
            self.scan={**msg,'received':time.monotonic()};self.sid=None
            self.uid.set(msg['uid']);self.direction.set(msg['direction'])
            self.observed.set(False);self.ready.set(False)
            self.status.set('Đã quét thẻ '+msg['uid']+'. Đối chiếu biển số và nhân viên để tạo phiên.')
        elif kind=='RESULT' and msg.get('sid')==self.sid:
            self.store.measure(self.sid,msg.get('adc'),msg.get('valid') is True)
            self.status.set('Đã lưu kết quả cảm biến. Chỉ phiên đạt mới được mở cổng.')
        elif kind=='OPENED' and msg.get('sid')==self.sid:
            self.store.acknowledge_gate(self.sid)
            self.status.set('ESP32 đã nhận lệnh mở. Quan sát và xác nhận khi xe thực sự đi qua.')
        elif kind in ('ERROR','READY'):
            self.status.set('ESP32: '+str(msg.get('message',kind)))
        self.refresh()

    def poll(self):
        try:
            if self.serial and self.serial.in_waiting:
                self.serial_buffer+=self.serial.read(self.serial.in_waiting)
                if len(self.serial_buffer)>16384: self.serial_buffer=b''
                while b'\n' in self.serial_buffer:
                    line,self.serial_buffer=self.serial_buffer.split(b'\n',1)
                    try:self.handle_device(json.loads(line))
                    except (ValueError,KeyError,TypeError):pass
            while not self.messages.empty():
                kind,value=self.messages.get_nowait()
                if kind=='camera':
                    self.capture={**value,'at':time.monotonic()};self.plate.set(value['plate'])
                    self.status.set('Đọc biển số: '+value['plate']+'. Bảo vệ kiểm tra lại trên xe. Ảnh: '+value['path'])
                else:self.status.set(value)
            if self.sid:
                s=self.store.session(self.sid)
                self.person_label.set(f"{s['employee_id']} · {s['name']} · {s['plate']} · {s['direction']} · {LABELS.get(s['state'],s['state'])} · ADC: {s['adc']} · ACK: {s['gate_ack']}")
        except Exception as exc:
            self.status.set('Lỗi kết nối: '+str(exc))
            if self.serial:self.serial.close();self.serial=None
            self.scan=None
        self.root.after(100,self.poll)

    def close(self):
        if self.serial:self.serial.close()
        self.store.close();self.root.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--demo',action='store_true',help='Isolated simulation; no physical gate commands')
    args=parser.parse_args()
    root=tk.Tk();App(root,args.demo);root.mainloop()
