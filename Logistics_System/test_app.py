"""Desktop integration checks; no physical device, camera or production database."""
import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
import app


class DesktopFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=app.BASE
        app.BASE=Path(self.temp.name)
        self.root=tk.Tk()
        self.ui=app.App(self.root,True)
        self.root.update()
        for var,value in zip(self.ui.fields,['NV001','Nguyễn Văn An','Giao nhận','59X112345','A1B2C3D4']):var.set(value)
        self.ui.save_person()

    def tearDown(self):
        self.ui.close()
        app.BASE=self.original
        self.temp.cleanup()

    def prepare(self,direction):
        self.ui.uid.set('A1B2C3D4');self.ui.plate.set('59X112345')
        self.ui.direction.set(direction);self.ui.observed.set(True)
        self.ui.start()

    def test_demo_full_cycle_and_statistics(self):
        self.prepare('IN');self.ui.open_gate();self.ui.passage()
        self.prepare('OUT');self.ui.ready.set(True);self.ui.adc.set('250');self.ui.measure()
        with self.assertRaises(ValueError):self.ui.open_gate()
        self.assertEqual(self.ui.store.employees()[0]['inside'],1)
        self.prepare('OUT');self.ui.ready.set(True);self.ui.adc.set('100');self.ui.measure()
        self.ui.open_gate();self.ui.passage();self.ui.refresh();self.root.update()
        self.assertEqual(self.ui.store.employees()[0]['inside'],0)
        self.assertIn('2 lần đo',self.ui.summary.get())
        self.assertIn('1 không đạt',self.ui.summary.get())

    def test_failed_replacement_revokes_old_grant(self):
        self.prepare('IN');old=self.ui.sid
        self.ui.plate.set('59X199999');self.ui.observed.set(True)
        with self.assertRaises(ValueError):self.ui.start()
        self.assertEqual(self.ui.store.session(old)['state'],'CANCELLED')
        with self.assertRaises(ValueError):self.ui.open_gate()

    def test_device_requires_scan_and_ack(self):
        self.ui.demo=False
        with self.assertRaises(ValueError):self.prepare('IN')
        self.ui.handle_device(dict(event='CARD',uid='A1B2C3D4',direction='IN',token='hardware-nonce'))
        self.ui.observed.set(True);self.ui.start()
        commands=[]
        self.ui.send=lambda command:commands.append(command)
        self.ui.open_gate()
        self.assertEqual(commands[0]['token'],'hardware-nonce')
        with self.assertRaises(ValueError):self.ui.passage()
        self.ui.handle_device(dict(event='OPENED',sid='wrong-session'))
        with self.assertRaises(ValueError):self.ui.passage()
        self.ui.handle_device(dict(event='OPENED',sid=self.ui.sid));self.ui.passage()
        self.assertEqual(self.ui.store.employees()[0]['inside'],1)

    def test_device_measurement_is_bound_to_session(self):
        self.prepare('IN');self.ui.open_gate();self.ui.passage()
        self.ui.demo=False
        self.ui.handle_device(dict(event='CARD',uid='A1B2C3D4',direction='OUT',token='next-nonce'))
        self.ui.plate.set('59X112345');self.ui.observed.set(True);self.ui.start()
        self.ui.handle_device(dict(event='RESULT',sid='stale-session',adc=100,valid=True))
        self.assertEqual(self.ui.store.session(self.ui.sid)['state'],'WAIT_TEST')
        self.ui.handle_device(dict(event='RESULT',sid=self.ui.sid,adc=250,valid=True))
        self.assertEqual(self.ui.store.session(self.ui.sid)['state'],'FAIL')
        with self.assertRaises(ValueError):self.ui.open_gate()


if __name__=='__main__':unittest.main()
