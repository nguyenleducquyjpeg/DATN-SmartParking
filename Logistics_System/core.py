"""Local, transactional business rules for a single logistics branch."""
import csv
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path


def plate_key(value):
    value = re.sub(r"[\s.\-]", "", value.upper())
    if not re.fullmatch(r"[0-9]{2}[A-Z][A-Z0-9]{1,2}[0-9]{4,5}", value):
        raise ValueError("Biển số không hợp lệ; ví dụ 59-X1 123.45")
    return value


def uid_key(value):
    value = re.sub(r"[\s:\-]", "", value.upper())
    if not re.fullmatch(r"(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})", value):
        raise ValueError("UID RFID phải có 4, 7 hoặc 10 byte dạng hex")
    return value


class Store:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS employees (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
          plate TEXT NOT NULL UNIQUE, uid TEXT NOT NULL UNIQUE,
          active INTEGER NOT NULL DEFAULT 1, inside INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, employee_id TEXT REFERENCES employees(id),
          name TEXT NOT NULL, plate TEXT NOT NULL, uid TEXT NOT NULL,
          direction TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
          expires REAL NOT NULL, threshold REAL NOT NULL, adc REAL,
          source TEXT NOT NULL, evidence TEXT NOT NULL, gate_ack INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
          employee_id TEXT, name TEXT, plate TEXT, uid TEXT, session_id TEXT,
          kind TEXT NOT NULL, detail TEXT NOT NULL);
        ''')

    def log(self, kind, detail, employee=None, session=None):
        e = dict(employee or {})
        self.db.execute("INSERT INTO events(at,employee_id,name,plate,uid,session_id,kind,detail) VALUES(?,?,?,?,?,?,?,?)",
                        (self.clock(), e.get('employee_id', e.get('id')), e.get('name'),
                         e.get('plate'), e.get('uid'), session, kind, detail))

    def employees(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM employees ORDER BY id")]

    def save_employee(self, employee_id, name, department, plate, uid):
        employee_id, name, department = employee_id.strip().upper(), name.strip(), department.strip()
        if not employee_id or not name or not department:
            raise ValueError("Nhập đủ mã nhân viên, họ tên và bộ phận")
        plate, uid = plate_key(plate), uid_key(uid)
        with self.db:
            old = self.db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
            if old and old['inside'] and (old['plate'] != plate or old['uid'] != uid):
                raise ValueError("Xe còn trong bãi: không đổi xe/thẻ trước khi hoàn tất lượt ra")
            self.db.execute("INSERT INTO employees(id,name,department,plate,uid) VALUES(?,?,?,?,?) "
                            "ON CONFLICT(id) DO UPDATE SET name=excluded.name,department=excluded.department,plate=excluded.plate,uid=excluded.uid",
                            (employee_id, name, department, plate, uid))
            self.db.execute("UPDATE sessions SET state='CANCELLED' WHERE employee_id=? AND state IN ('WAIT_TEST','AUTHORIZED')", (employee_id,))
            self.log('EMPLOYEE_SAVED', 'Cập nhật hồ sơ; hủy phiên chờ cũ',
                     dict(id=employee_id, name=name, plate=plate, uid=uid))

    def set_active(self, employee_id, active):
        with self.db:
            e = self.db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
            if not e:
                raise ValueError("Không tìm thấy nhân viên")
            self.db.execute("UPDATE employees SET active=? WHERE id=?", (int(active), employee_id))
            self.db.execute("UPDATE sessions SET state='CANCELLED' WHERE employee_id=? AND state IN ('WAIT_TEST','AUTHORIZED')", (employee_id,))
            self.log('EMPLOYEE_ACTIVE', str(bool(active)), e)

    def expire(self):
        with self.db:
            for s in self.db.execute("SELECT * FROM sessions WHERE state IN ('WAIT_TEST','AUTHORIZED') AND expires<=?", (self.clock(),)).fetchall():
                self.db.execute("UPDATE sessions SET state='EXPIRED' WHERE id=?", (s['id'],))
                self.log('EXPIRED', 'Hết hạn phiên; phải đối chiếu lại', s, s['id'])

    def start(self, uid, plate, direction, threshold, source='MANUAL', evidence=''):
        self.expire()
        if direction not in ('IN', 'OUT') or source not in ('MANUAL', 'CAMERA', 'DEMO'):
            raise ValueError("Hướng/nguồn không hợp lệ")
        if not math.isfinite(float(threshold)) or not 0 < float(threshold) < 4095:
            raise ValueError("Ngưỡng ADC thử nghiệm phải lớn hơn 0 và nhỏ hơn 4095")
        uid, plate = uid_key(uid), plate_key(plate)
        error = None
        with self.db:
            # An attempted replacement at this lane revokes the previous permission,
            # even when the new card/plate is rejected.
            self.db.execute("UPDATE sessions SET state='CANCELLED' WHERE direction=? AND state IN ('WAIT_TEST','AUTHORIZED')", (direction,))
            e = self.db.execute("SELECT * FROM employees WHERE uid=?", (uid,)).fetchone()
            if not e: error = 'Thẻ chưa đăng ký'
            elif not e['active']: error = 'Nhân viên/thẻ đã ngừng hiệu lực'
            elif e['plate'] != plate: error = 'Biển số không khớp xe đăng ký'
            elif bool(e['inside']) != (direction == 'OUT'): error = 'Trạng thái xe không phù hợp với hướng vào/ra'
            if error:
                self.log('DENIED', error + ' | hướng=' + direction + ' | biển đọc=' + plate,
                         e or dict(uid=uid, plate=plate))
            else:
                # One pending vehicle per physical lane; a new scan invalidates an older grant.
                self.db.execute("UPDATE sessions SET state='CANCELLED' WHERE state IN ('WAIT_TEST','AUTHORIZED') AND (direction=? OR employee_id=?)", (direction, e['id']))
                sid = uuid.uuid4().hex
                state = 'AUTHORIZED' if direction == 'IN' else 'WAIT_TEST'
                self.db.execute("INSERT INTO sessions(id,employee_id,name,plate,uid,direction,state,created,expires,threshold,source,evidence) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                (sid,e['id'],e['name'],plate,uid,direction,state,self.clock(),self.clock()+90,float(threshold),source,evidence))
                self.log(state, 'Đối chiếu thẻ và xe đăng ký thành công', e, sid)
        if error: raise ValueError(error)
        return self.session(sid)

    def session(self, sid):
        self.expire()
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row: raise ValueError("Không tìm thấy phiên")
        return dict(row)

    def measure(self, sid, value, valid=True):
        s = self.session(sid)
        if s['state'] != 'WAIT_TEST': raise ValueError("Phiên không chờ đo hoặc đã hết hạn")
        try:
            value = float(value)
            valid = valid and math.isfinite(value) and 0 < value < 4095
        except (ValueError, TypeError):
            valid, value = False, None
        if not valid: value = None
        result = 'ERROR' if not valid else ('FAIL' if value >= s['threshold'] else 'PASS')
        with self.db:
            self.db.execute("UPDATE sessions SET state=?,adc=?,expires=? WHERE id=?",
                            ('AUTHORIZED' if result == 'PASS' else result, value, self.clock()+30, sid))
            self.log('TEST_'+result, f'ADC={value}; ngưỡng={s["threshold"]}; nguồn={s["source"]}', s, sid)
        return self.session(sid)

    def acknowledge_gate(self, sid):
        s = self.session(sid)
        if s['state'] != 'AUTHORIZED': raise ValueError("Không có quyền mở cổng còn hiệu lực")
        with self.db:
            self.db.execute("UPDATE sessions SET gate_ack=1 WHERE id=?", (sid,))
            self.log('GATE_ACK', 'Thiết bị xác nhận đã nhận lệnh mở (không phải cảm biến vị trí)', s, sid)

    def confirm_passage(self, sid):
        s = self.session(sid)
        if s['state'] != 'AUTHORIZED' or not s['gate_ack']:
            raise ValueError("Chưa có xác nhận lệnh mở cổng hoặc phiên đã hết hạn")
        with self.db:
            e = self.db.execute("SELECT * FROM employees WHERE id=?", (s['employee_id'],)).fetchone()
            if not e['active'] or e['plate'] != s['plate'] or e['uid'] != s['uid']:
                raise ValueError("Hồ sơ đã thay đổi, cần đối chiếu lại")
            if bool(e['inside']) != (s['direction'] == 'OUT'):
                raise ValueError("Trạng thái xe đã thay đổi")
            self.db.execute("UPDATE employees SET inside=? WHERE id=?", (int(s['direction']=='IN'),s['employee_id']))
            self.db.execute("UPDATE sessions SET state='COMPLETED' WHERE id=?", (sid,))
            self.log('PASSAGE_'+s['direction'], 'Bảo vệ xác nhận xe đã qua cổng', s, sid)

    def events(self, query='', day=''):
        # Local workstation timezone is used in the desktop application.
        return [dict(r) for r in self.db.execute("SELECT *,datetime(at,'unixepoch','localtime') AS local_time FROM events "
            "WHERE (coalesce(employee_id,'') LIKE ? OR coalesce(name,'') LIKE ? OR coalesce(plate,'') LIKE ?) "
            "AND date(at,'unixepoch','localtime') LIKE ? ORDER BY id DESC",
            ('%'+query+'%', '%'+query+'%', '%'+query+'%', day+'%'))]

    def export_csv(self, path, query='', day=''):
        rows = self.events(query, day)
        fields = ['id','local_time','employee_id','name','plate','uid','session_id','kind','detail']
        with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fields, extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                # Prevent spreadsheet formula evaluation in exported user-entered text.
                writer.writerow({k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for k,v in row.items()})

    def close(self):
        self.db.close()
