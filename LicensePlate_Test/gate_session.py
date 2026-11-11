"""Presentation state for a lane. Only matching firmware events may set decisions."""
from dataclasses import dataclass, field
import time

LABELS = {
    'IDLE':'Chờ quét thẻ', 'WAIT_CAMERA':'Đã quét thẻ · chờ đối chiếu biển số',
    'TESTING':'Đang kiểm tra nồng độ cồn', 'PASS':'Kết quả đo đạt · chưa xác nhận mở cổng',
    'FAIL':'Không đạt · không cho mở cổng', 'ERROR':'Lỗi · không cho mở cổng',
    'DENIED':'Từ chối yêu cầu', 'OPENED':'Đã gửi lệnh mở cổng',
    'CLOSED':'Đã gửi lệnh đóng cổng', 'UNKNOWN':'Chưa nhận được trạng thái tiếp theo',
}
REASONS = {
    'UNREGISTERED_CARD':'Thẻ chưa được đăng ký', 'INACTIVE_EMPLOYEE':'Hồ sơ đã ngừng hiệu lực',
    'CAMERA_NOT_MATCHED':'Chưa nhận đúng biển số trong thời gian chờ',
    'CAMERA_SESSION_EXPIRED':'Yêu cầu camera đã hết hạn', 'CARD_PLATE_MISMATCH':'Thẻ và biển số không khớp',
    'INVALID_VEHICLE_STATE':'Trạng thái trong/ngoài bưu cục không phù hợp',
    'PARKING_FULL':'Khu vực xe đã hết chỗ', 'CONFIG_READ_ERROR':'Không đọc được cấu hình',
    'INVALID_CAPACITY':'Cấu hình sức chứa không hợp lệ', 'PROFILE_READ_ERROR':'Không đọc được hồ sơ',
    'STATE_READ_ERROR':'Không đọc được trạng thái xe', 'NO_CAMERA_SESSION':'Chưa có yêu cầu camera',
    'ADC_NOT_CONFIGURED':'Chưa cấu hình ngưỡng ADC trên web', 'SAVE_TEST_FAILED':'Không lưu được kết quả đo',
    'PROFILE_CHANGED':'Hồ sơ đã thay đổi; cần quét lại', 'SAVE_STATE_FAILED':'Không lưu được trạng thái cổng',
    'RAW_ADC_UNCALIBRATED':'ADC thử nghiệm, chưa hiệu chuẩn mg/L',
}


@dataclass
class LaneState:
    lane: str
    scan_id: str = ''
    uid: str = ''
    person: dict = field(default_factory=dict)
    plate: str = ''
    source: str = ''
    plate_at: float = 0
    scan_at: float = 0
    status_at: float = 0
    sequence: int = -1
    state: str = 'IDLE'
    reason: str = ''
    adc: object = None
    threshold: object = None
    request_id: str = ''

    def scan(self, event, person):
        stamp = event.get('timestamp', 0)
        if not event.get('eventId') or event['eventId'] == self.scan_id or stamp < self.scan_at:
            return False
        self.scan_id, self.uid, self.person = event['eventId'], event['rfid'], person or {}
        self.scan_at = self.status_at = stamp
        self.sequence = -1
        self.state, self.reason = 'WAIT_CAMERA', ''
        self.adc = self.threshold = None
        self.request_id = ''
        return True

    def observe(self, plate, source='CAMERA', now=None):
        self.plate, self.source = plate, source
        self.plate_at = (time.time() if now is None else now)*1000

    def status(self, event):
        if event.get('scanId') != self.scan_id or event.get('rfid') != self.uid or not self.scan_id:
            return False
        sequence = event.get('sequence', -1)
        if sequence <= self.sequence or event.get('trangThai') not in LABELS:
            return False
        self.sequence = sequence
        self.state = event['trangThai']
        self.status_at = event.get('timestamp', self.status_at)
        self.reason = event.get('lyDo', '')
        self.request_id = event.get('requestId', self.request_id)
        if event.get('adc') is not None: self.adc = event['adc']
        if event.get('nguongADC') is not None: self.threshold = event['nguongADC']
        return True

    def comparison(self, now=None):
        now_ms = (time.time() if now is None else now)*1000
        if not self.scan_id: return 'Chưa quét thẻ'
        if not self.person: return 'Không tìm thấy hồ sơ'
        if self.person.get('hoatDong') is not True: return 'Hồ sơ đã ngừng hiệu lực'
        if not self.plate or now_ms-self.plate_at > 30000: return 'Chờ biển số mới'
        return 'KHỚP xe đăng ký' if self.plate == self.person.get('bienSo') else 'KHÔNG KHỚP xe đăng ký'

    def display_state(self, now=None):
        now_ms = (time.time() if now is None else now)*1000
        if self.state in ('WAIT_CAMERA','TESTING','PASS','OPENED') and now_ms-self.status_at > 90000:
            return LABELS['UNKNOWN']+' · cần kiểm tra thiết bị'
        return LABELS[self.state]
