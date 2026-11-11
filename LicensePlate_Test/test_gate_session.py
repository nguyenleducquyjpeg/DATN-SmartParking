import time
import unittest
from gate_session import LaneState


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.s=LaneState('OUT')
        self.now=int(time.time()*1000)
        self.person=dict(maNhanVien='001',hoTen='A',bienSo='76G108216',hoatDong=True)
        self.scan=dict(eventId='scan-1',rfid='A31695DC',timestamp=self.now)
        self.s.scan(self.scan,self.person)

    def status(self,**kwargs):
        return dict(scanId='scan-1',rfid='A31695DC',timestamp=self.now,sequence=1,trangThai='PASS',**kwargs)

    def test_another_card_or_session_cannot_receive_result(self):
        e=self.status();e['scanId']='old'
        self.assertFalse(self.s.status(e))
        e=self.status();e['rfid']='11223344'
        self.assertFalse(self.s.status(e));self.assertIsNone(self.s.adc)

    def test_sequence_cannot_regress(self):
        e=self.status();e.update(sequence=3,trangThai='CLOSED',adc=100,nguongADC=200)
        self.assertTrue(self.s.status(e));self.assertFalse(self.s.status(self.status()))
        self.assertEqual(self.s.state,'CLOSED');self.assertEqual(self.s.adc,100)

    def test_retest_clears_old_measurement(self):
        self.s.status(self.status(adc=300,nguongADC=200))
        self.s.scan(dict(self.scan,eventId='scan-2',timestamp=self.now+1000),self.person)
        self.assertIsNone(self.s.adc);self.assertEqual(self.s.state,'WAIT_CAMERA')
        self.assertFalse(self.s.status(self.status()))

    def test_duplicate_scan_does_not_clear_result(self):
        self.s.status(self.status(adc=100))
        self.assertFalse(self.s.scan(self.scan,self.person));self.assertEqual(self.s.adc,100)

    def test_comparison_and_staleness(self):
        self.s.observe('76G108216',now=self.now/1000)
        self.assertEqual(self.s.comparison(self.now/1000),'KHỚP xe đăng ký')
        self.assertEqual(self.s.comparison(self.now/1000+31),'Chờ biển số mới')
        self.s.observe('59X112345',now=self.now/1000)
        self.assertIn('KHÔNG KHỚP',self.s.comparison(self.now/1000))

    def test_two_lanes_are_independent(self):
        other=LaneState('IN');other.scan(dict(self.scan,eventId='other'),{'hoTen':'B'})
        self.s.status(self.status(adc=100))
        self.assertEqual(other.state,'WAIT_CAMERA');self.assertIsNone(other.adc)

    def test_missing_status_is_unknown_not_success(self):
        self.assertIn('Chưa nhận',self.s.display_state(self.now/1000+91))
        self.assertNotEqual(self.s.state,'OPENED')


if __name__=='__main__':unittest.main()
