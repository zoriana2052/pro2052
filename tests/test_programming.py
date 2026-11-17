import json
import sys

TEST_PORT = "/dev/cu.usbserial-TEST" if sys.platform == "darwin" else "COM5"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import programming as p
import radio

OLD=p.parse_channel(b'C022 F04502250 TF DF LF AF RF N00\r',22)
NEW=p.parse_channel(b'C022 F04603250 TF DF LF AF RF N00\r',22)

class FakePort:
    def __init__(self): self.writes=[]
    def write(self,data): self.writes.append(data); return len(data)

class ProgrammingTests(unittest.TestCase):
    def test_valid_encoding_and_bands(self):
        for value,digits in [('450.2250','04502250'),('467,6625','04676625'),('1300','13000000'),('179.75','01797500')]:
            self.assertEqual(p.frequency_digits(value),digits)
        for value in ['0','NaN','Infinity','450.22501','450.226','54.005','824','868.9999','PM022','450\rAC','179.8']:
            with self.subTest(value=value),self.assertRaises(p.ProgrammingError): p.frequency_digits(value)

    def test_channel_bounds_and_readonly_remain(self):
        for value in ['0','1001','-1','1\rAC','1.0']:
            with self.assertRaises(p.ProgrammingError): p.channel_number(value)
        self.assertEqual(p.channel_number('001'),1)
        with self.assertRaises(ValueError): radio.wire('PM022 04603250')

    def test_reject_unknown_echo_wrong_channel(self):
        for raw in [b'OK\r',b'PM022\r',b'NG\r',b'F04502250',b'C023 F04502250 TF\r',b'F04502250\rOK\r']:
            with self.assertRaises(p.ProgrammingError): p.parse_channel(raw,22)
        self.assertEqual(p.parse_channel(b'F00000000\r',22).digits,'00000000')
        self.assertTrue(p.parse_channel(b'C022 F04502250 TN\r',22).trunked)

    def transaction(self,root,port):
        return p.program_channel(port,OLD,'460.325',root,Path(root)/'log.csv',TEST_PORT,19200)

    def test_backup_before_write_and_verified_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            port=FakePort()
            def write(data):
                backups=list(Path(folder).glob('channel-backups/*.json'))
                self.assertEqual(len(backups),1)
                self.assertEqual(json.loads(backups[0].read_text())['old_frequency_mhz'],'450.2250')
                return FakePort.write(port,data)
            port.write=write
            with patch('programming.read_channel',side_effect=[OLD,NEW]) as read,patch('radio.capture',side_effect=[b'',b'OK\r']):
                result,backup=self.transaction(folder,port)
            self.assertEqual(result,NEW)
            self.assertEqual(read.call_count,2)
            self.assertEqual(port.writes,[b'PM022 04603250\r'])
            self.assertTrue(backup.exists())

    def test_changed_channel_aborts_before_write(self):
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',return_value=NEW):
            port=FakePort()
            with self.assertRaisesRegex(p.ProgrammingError,'changed'): self.transaction(folder,port)
            self.assertEqual(port.writes,[])

    def test_backup_io_failure_aborts_before_write(self):
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',return_value=OLD),patch('programming.os.fsync',side_effect=OSError('disk full')):
            port=FakePort()
            with self.assertRaises(OSError): self.transaction(folder,port)
            self.assertEqual(port.writes,[])

    def test_timeout_rejection_mismatch_never_retry(self):
        for ack,result in [(b'',NEW),(b'NG\r',OLD),(b'OK\r',OLD)]:
            with self.subTest(ack=ack),tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[OLD,result]),patch('radio.capture',side_effect=[b'',ack]):
                port=FakePort()
                with self.assertRaisesRegex(p.ProgrammingError,'uncertain'): self.transaction(folder,port)
                self.assertEqual(len(port.writes),1)

    def test_no_writes_to_trunked_or_same_frequency(self):
        for old,freq in [(p.Channel(22,OLD.digits,b'TN',True),'460.325'),(OLD,'450.225')]:
            with tempfile.TemporaryDirectory() as folder:
                port=FakePort()
                with self.assertRaises(p.ProgrammingError): p.program_channel(port,old,freq,folder,Path(folder)/'log.csv',TEST_PORT,19200)
                self.assertEqual(port.writes,[])

    def test_stale_data_aborts_write(self):
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',return_value=OLD),patch('radio.capture',return_value=b'garbage'):
            port=FakePort()
            with self.assertRaisesRegex(p.ProgrammingError,'stale'): self.transaction(folder,port)
            self.assertEqual(port.writes,[])

class ProgrammingUITests(unittest.TestCase):
    def test_preview_confirmation_and_serial_exclusion(self):
        import tkinter as tk
        import window
        root=tk.Tk(); root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder,patch.object(window.App,'refresh'):
                app=window.App(root,Path(folder)); panel=app.programming
                app.port.set(TEST_PORT);app.baud.set('19200');panel.channel.set('22')
                panel.frequency.set('460.325')
                with patch.object(panel,'show_error') as error,patch.object(panel,'launch') as launch:
                    panel.write(); self.assertEqual(error.call_args[0][0].code,'read_first');launch.assert_not_called()
                panel.preview=((TEST_PORT,19200,22),OLD)
                import inventory
                panel.inventory=inventory.Inventory(TEST_PORT,19200,True,
                    {i:p.Channel(i,'00000000',b'F00000000\r') for i in range(1000)})
                panel.inventory.records[22]=OLD
                with patch('programming_ui.messagebox.askyesno',return_value=False),patch.object(panel,'launch') as launch:
                    panel.write();launch.assert_not_called()
                with patch('programming_ui.messagebox.askyesno',return_value=True),patch.object(panel,'launch') as launch:
                    panel.write(); self.assertEqual(launch.call_args[0],('write',(TEST_PORT,19200,22),OLD,'460.3250'))
                app.worker=object()
                with patch('programming_ui.messagebox.showinfo'),patch.object(panel,'launch') as launch:
                    panel.read(); launch.assert_not_called()
                app.worker=None
                panel.busy=True
                with patch('window.threading.Thread') as worker:
                    app.start(); worker.assert_not_called()
                panel.busy=False
                app.language_ui.language='en';app.language_ui.apply()
                self.assertEqual(panel.read_button.cget('text'),'Read channel')
                self.assertEqual(app.notebook.tab(1,'text'),'Channel programming')
                app.language_ui.language='uk';app.language_ui.apply()
                self.assertEqual(panel.read_button.cget('text'),'Прочитати канал')
        finally: root.destroy()

if __name__=='__main__': unittest.main()
