from pathlib import Path
import unittest
from unittest.mock import patch
import platform_support as p
from app_storage import load_connection
import tempfile,json

class MacPortTests(unittest.TestCase):
    def test_device_case_is_preserved(self):
        self.assertEqual(p.normalize_port(' /dev/cu.usbserial-Aa19 '),'/dev/cu.usbserial-Aa19')
        self.assertEqual(p.normalize_port('com5'),'COM5')
    @patch.object(p.sys,'platform','darwin')
    def test_mac_ports_and_rejection(self):
        self.assertTrue(p.valid_port('/dev/cu.usbserial-Aa19'))
        self.assertTrue(p.valid_port('/dev/tty.usbmodem101'))
        for bad in ('COM5','/dev/cu.x/../file','/tmp/file',''):
            self.assertFalse(p.valid_port(bad))
    @patch.object(p.sys,'platform','darwin')
    def test_mac_storage(self):
        self.assertEqual(p.default_data_folder(),Path.home()/'Library/Application Support/PRO2052')
    @patch.object(p.sys,'platform','darwin')
    def test_saved_mac_connection(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'connection.json';f.write_text(json.dumps({'port':'/dev/cu.usbserial-Aa19','baud':'19200'}))
            self.assertEqual(load_connection(f)['port'],'/dev/cu.usbserial-Aa19')
