import csv
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import inventory as m
import programming as p
from test_programming import FakePort

class InventoryTests(unittest.TestCase):
    def test_all_addresses_empty_and_duplicates(self):
        calls=[]
        def read(port,address,*args):
            calls.append(address)
            digits='04353750' if address in (22,198) else '00000000'
            return p.Channel(address,digits,f'C{address:03d} F{digits} TF\r'.encode())
        with tempfile.TemporaryDirectory() as folder,patch('inventory.read_address',side_effect=read):
            result=m.read_all(None,'COM5',19200,folder,Path(folder)/'raw.csv',threading.Event(),lambda *args:None,True)
            self.assertTrue(result.complete)
            self.assertEqual(set(calls),set(range(1000)))
            self.assertEqual(len(calls),1000)
            self.assertEqual(result.duplicates('04353750',198),[22])
            self.assertEqual(result.duplicates('00000000'),[])
            with open(result.path,encoding='utf-8-sig',newline='') as file: rows=list(csv.DictReader(file))
            self.assertEqual(len(rows),1000)
            self.assertEqual(rows[-1]['channel'],'1000')
            self.assertEqual(rows[197]['duplicates'],'022')

    def test_mapping_is_never_assumed(self):
        inv=m.Inventory('COM5',19200,False,{i:p.Channel(i,'00000000',b'F00000000\r') for i in range(1000)})
        self.assertFalse(inv.complete)
        self.assertEqual(inv.label(0),'000 (?)')
        inv.confirmed_last=True
        self.assertTrue(inv.complete)

    def test_cancel_and_errors_preserve_partial_snapshot(self):
        for failure in (False,True):
            stop=threading.Event()
            def progress(count,*args):
                if not failure: stop.set()
            def read(port,address,*args):
                if failure: raise p.ProgrammingError('response','timeout')
                return p.Channel(address,'00000000',b'F00000000\r')
            with tempfile.TemporaryDirectory() as folder,patch('inventory.read_address',side_effect=read):
                result=m.read_all(None,'COM5',19200,folder,Path(folder)/'raw.csv',stop,progress,True)
                self.assertFalse(result.complete)
                self.assertTrue(Path(result.path).exists())
                self.assertEqual(len(result.errors) if failure else len(result.records),3 if failure else 1)

    def test_manual_1000_mapping_requires_matching_read_and_manual_mode(self):
        raw=b'C000 F04353750 TF DF LF AF RF N00\r'
        with patch('radio.exchange',side_effect=[b'MD01\r',raw,raw]) as query:
            result=m.verify_last_channel(None,'log','COM5',19200)
            self.assertEqual(result.number,0)
            self.assertEqual([call.args[1] for call in query.call_args_list],['MD','MA','PM000'])
        for replies in ([b'MD00\r'],[b'MD01\r',b'C198 F04353750 TF\r'],[b'MD01\r',raw,b'C000 F00000000 TF\r']):
            with patch('radio.exchange',side_effect=replies),self.assertRaises(p.ProgrammingError):
                m.verify_last_channel(None,'log','COM5',19200)

    def test_real_hardware_reply_after_writing_empty_channel(self):
        old=p.parse_channel(b'C198 F00000000 TF DF LF AF RF N00\r',198)
        raw=b'C198 F04353750 TF DF LF AF RF N00\r'
        new=p.parse_channel(raw,198)
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[old,new]),patch('radio.capture',side_effect=[b'',raw]):
            port=FakePort()
            result,backup=p.program_channel(port,old,'435.3750',folder,Path(folder)/'raw.csv','COM5',19200)
            self.assertEqual(result,new)
            self.assertEqual(port.writes,[b'PM198 04353750\r'])

    def test_returned_record_must_match_channel_frequency_and_readback(self):
        old=p.parse_channel(b'C198 F00000000 TF\r',198)
        new=p.parse_channel(b'C198 F04353750 TF\r',198)
        for reply,actual in [(b'C199 F04353750 TF\r',new),(b'C198 F04353750 TF\r',old),(b'C198 F04353750 TN\r',new),(b'C198 F04350000 TF\r',new)]:
            with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[old,actual]),patch('radio.capture',side_effect=[b'',reply]):
                port=FakePort()
                with self.assertRaisesRegex(p.ProgrammingError,'uncertain'):
                    p.program_channel(port,old,'435.3750',folder,Path(folder)/'raw.csv','COM5',19200)
                self.assertEqual(len(port.writes),1)

    def test_ui_blocks_duplicates_partial_and_wrong_port(self):
        import tkinter as tk
        import window
        root=tk.Tk();root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder,patch.object(window.App,'refresh'):
                app=window.App(root,Path(folder));panel=app.programming
                app.port.set('COM5');app.baud.set('19200');panel.channel.set('198');panel.frequency.set('435.375')
                old=p.Channel(198,'00000000',b'F00000000\r')
                panel.preview=(('COM5',19200,198),old)
                with patch.object(panel,'show_error') as error,patch.object(panel,'launch') as launch:
                    panel.write(); self.assertEqual(error.call_args[0][0].code,'inventory_required');launch.assert_not_called()
                    panel.inventory=m.Inventory('COM5',19200,True,{i:p.Channel(i,'00000000',b'F00000000\r') for i in range(1000)})
                    panel.inventory.records[22]=p.Channel(22,'04353750',b'F04353750\r')
                    panel.write(); self.assertEqual(error.call_args[0][0].code,'duplicate');launch.assert_not_called()
                    panel.inventory.port='COM4'
                    panel.write(); self.assertEqual(error.call_args[0][0].code,'inventory_required');launch.assert_not_called()
        finally: root.destroy()

if __name__=='__main__':unittest.main()
