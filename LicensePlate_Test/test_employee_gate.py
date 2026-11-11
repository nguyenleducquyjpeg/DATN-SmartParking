"""Test dashboard methods without importing camera models or Firebase credentials."""
import ast
import time
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from employee_registry import Registry, normalize_plate


class FakeDB:
    def __init__(self): self.values={};self.writes=[]
    def reference(self,path):
        db=self
        class Ref:
            def get(self): return db.values.get(path)
            def set(self,value): db.writes.append((path,value));db.values[path]=value
        return Ref()


class GateTests(unittest.TestCase):
    def setUp(self):
        self.db=FakeDB()
        self.person=dict(maNhanVien='001',hoTen='Quý',boPhan='Shipper',rfid='A31695DC',bienSo='76G108216',hoatDong=True)
        self.db.values.update({'HoSoNhanVien/theRFID/A31695DC':'001','HoSoNhanVien/bienSo/76G108216':'001','HoSoNhanVien/nhanVien/001':self.person})
        source=ast.parse(Path(__file__).with_name('dashboard_parking.py').read_text(encoding='utf-8'))
        cls=next(n for n in source.body if isinstance(n,ast.ClassDef))
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('publish_vehicle','process_in_db','process_out_db')]
        module=ast.Module(body=methods,type_ignores=[])
        env=dict(db=self.db,time=time,uuid=uuid,datetime=datetime,normalize_plate=normalize_plate)
        exec(compile(module,'dashboard_methods','exec'),env)
        self.app=SimpleNamespace(last_publish={},registry=Registry(self.db),employee_panel=SimpleNamespace(show=lambda p:None),banner_lbl=SimpleNamespace(config=lambda **kw:None),show_entry_snapshot_for_plate=lambda p:None)
        self.publish=lambda direction:env['publish_vehicle'](self.app,'76-G1 082.16',direction)

    def test_known_employee_publishes_identity_and_expiring_session(self):
        self.assertTrue(self.publish('IN'))
        node,data=self.db.writes[-1]
        self.assertEqual(node,'XeDangVao');self.assertEqual(data['maNhanVien'],'001')
        self.assertEqual(data['timestamp'],{'.sv':'timestamp'});self.assertEqual(len(data['requestId']),32)

    def test_unregistered_and_inactive_vehicles_never_publish(self):
        self.person['hoatDong']=False
        with self.assertRaises(ValueError):self.publish('IN')
        self.assertFalse(self.db.writes)
        self.db.values.pop('HoSoNhanVien/bienSo/76G108216')
        with self.assertRaises(ValueError):self.publish('IN')

    def test_out_requires_inside_state_and_correct_uid(self):
        with self.assertRaises(ValueError):self.publish('OUT')
        self.db.values['XeTrongBai/A31695DC']=True
        self.assertTrue(self.publish('OUT'));self.assertEqual(self.db.writes[-1][1]['rfid'],'A31695DC')

    def test_duplicate_entry_rejected_and_lookup_by_card(self):
        self.db.values['XeTrongBai/A31695DC']=True
        with self.assertRaises(ValueError):self.publish('IN')
        self.assertEqual(Registry(self.db).by_uid('A31695DC')['hoTen'],'Quý')
        self.assertIsNone(Registry(self.db).by_uid('11223344'))

    def test_camera_never_replaces_identity_of_scanned_employee(self):
        self.app.employee_panel.show=Mock()
        self.assertTrue(self.publish('IN'))
        self.app.employee_panel.show.assert_not_called()

if __name__=='__main__':unittest.main()
