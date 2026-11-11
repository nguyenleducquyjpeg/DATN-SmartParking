import tempfile
import unittest
from pathlib import Path
from core import Store, plate_key, uid_key


class BusinessRules(unittest.TestCase):
    def setUp(self):
        self.now=1000000.
        self.s=Store(':memory:',clock=lambda:self.now)
        self.s.save_employee('NV001','Nguyễn An','Giao nhận','59-X1 123.45','A1 B2 C3 D4')

    def tearDown(self):self.s.close()

    def start(self,direction='IN',uid='A1B2C3D4',plate='59X112345'):
        return self.s.start(uid,plate,direction,200,'DEMO')

    def enter(self):
        s=self.start();self.s.acknowledge_gate(s['id']);self.s.confirm_passage(s['id'])

    def test_normal_complete_cycle(self):
        self.enter();s=self.start('OUT')
        self.assertEqual(self.s.measure(s['id'],100)['state'],'AUTHORIZED')
        self.s.acknowledge_gate(s['id']);self.s.confirm_passage(s['id'])
        self.assertEqual(self.s.employees()[0]['inside'],0)
        self.assertEqual(sum(e['kind']=='TEST_PASS' for e in self.s.events()),1)

    def test_unknown_mismatch_and_inactive(self):
        for uid,plate in [('FFFFFFFF','59X112345'),('A1B2C3D4','59X199999')]:
            with self.assertRaises(ValueError):self.start(uid=uid,plate=plate)
        self.s.set_active('NV001',False)
        with self.assertRaises(ValueError):self.start()
        self.assertEqual(sum(e['kind']=='DENIED' for e in self.s.events()),3)

    def test_unique_vehicle_and_card(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):self.s.save_employee('NV002','B','Giao nhận','59X112345','11223344')
        with self.assertRaises(sqlite3.IntegrityError):self.s.save_employee('NV002','B','Giao nhận','59X199999','A1B2C3D4')
        self.assertEqual(len(self.s.employees()),1)

    def test_fail_and_retest_are_separate(self):
        self.enter();s=self.start('OUT')
        self.assertEqual(self.s.measure(s['id'],200)['state'],'FAIL')
        with self.assertRaises(ValueError):self.s.acknowledge_gate(s['id'])
        self.assertEqual(self.s.employees()[0]['inside'],1)
        t=self.start('OUT');self.s.measure(t['id'],100)
        self.assertEqual(sum(e['kind'].startswith('TEST_') for e in self.s.events()),2)

    def test_error_readings_fail_closed(self):
        self.enter()
        for value in [None,'bad',float('nan'),float('inf'),-1,0,4095,5000]:
            s=self.start('OUT');self.assertEqual(self.s.measure(s['id'],value)['state'],'ERROR')
            with self.assertRaises(ValueError):self.s.confirm_passage(s['id'])
        s=self.start('OUT');self.assertEqual(self.s.measure(s['id'],100,False)['state'],'ERROR')

    def test_expired_and_replayed_results(self):
        self.enter();s=self.start('OUT');self.now+=91
        with self.assertRaises(ValueError):self.s.measure(s['id'],100)
        t=self.start('OUT');self.s.measure(t['id'],100)
        with self.assertRaises(ValueError):self.s.measure(t['id'],100)
        self.now+=31
        with self.assertRaises(ValueError):self.s.acknowledge_gate(t['id'])

    def test_gate_ack_and_passage_are_distinct(self):
        s=self.start()
        with self.assertRaises(ValueError):self.s.confirm_passage(s['id'])
        self.s.acknowledge_gate(s['id'])
        self.assertEqual(self.s.employees()[0]['inside'],0)
        self.s.confirm_passage(s['id'])
        with self.assertRaises(ValueError):self.s.confirm_passage(s['id'])

    def test_duplicate_entry_and_missing_exit(self):
        with self.assertRaises(ValueError):self.start('OUT')
        self.enter()
        with self.assertRaises(ValueError):self.start('IN')

    def test_profile_change_cancels_grant_and_keeps_history(self):
        s=self.start()
        self.s.save_employee('NV001','Tên mới','Giao nhận','59X199999','11223344')
        with self.assertRaises(ValueError):self.s.acknowledge_gate(s['id'])
        old=self.s.session(s['id'])
        self.assertEqual(old['name'],'Nguyễn An');self.assertEqual(old['plate'],'59X112345')

    def test_cannot_change_inside_vehicle(self):
        self.enter()
        with self.assertRaises(ValueError):self.s.save_employee('NV001','A','Giao nhận','59X199999','11223344')

    def test_one_pending_session_per_lane(self):
        s=self.start();t=self.start()
        self.assertEqual(self.s.session(s['id'])['state'],'CANCELLED')
        self.assertEqual(t['state'],'AUTHORIZED')

    def test_threshold_and_normalization(self):
        self.assertEqual(plate_key('59-X1 123.45'),'59X112345')
        self.assertEqual(uid_key('a1:b2:c3:d4'),'A1B2C3D4')
        for value in [0,-1,4095,float('nan')]:
            with self.assertRaises(ValueError):self.s.start('A1B2C3D4','59X112345','IN',value)

    def test_export_filters_and_formula_escape(self):
        self.s.save_employee('NV002','=1+1','Giao nhận','59X199999','11223344')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'events.csv';self.s.export_csv(path,'NV002')
            text=path.read_text(encoding='utf-8-sig')
            self.assertIn("'=1+1",text);self.assertNotIn('NV001',text)


if __name__=='__main__':unittest.main()
