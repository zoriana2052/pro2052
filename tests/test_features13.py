import csv
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import channel_tools as c
import programming as p
import inventory as m
import frequency_search as s


def inv():
    return m.Inventory('COM5',19200,True,{n:p.Channel(n,'00000000',f'C{n:03d} F00000000 TF\r'.encode()) for n in range(1000)})

class PlanTests(unittest.TestCase):
    def test_csv_allocation_semicolon_decimal_and_channel1000(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'input.csv'
            file.write_text('channel;frequency_mhz\n1000;435,3750\n22;450,2250\n',encoding='utf-8')
            self.assertEqual(c.load_file(file),{0:'04353750',22:'04502250'})
            file.write_text('frequency_mhz\n435.3750\n450.2250\n',encoding='utf-8')
            self.assertEqual(c.load_file(file,inv(),start=5,reserved={5}),{6:'04353750',7:'04502250'})

    def test_bad_csv_is_rejected(self):
        for text in ['channel,frequency_mhz\n2,435.375\n2,450.225\n','channel,frequency_mhz\n2,NaN\n','channel,frequency_mhz\n1001,435.375\n','channel,frequency_mhz\n2,435.375,extra\n']:
            with tempfile.TemporaryDirectory() as folder:
                file=Path(folder)/'x.csv';file.write_text(text)
                with self.assertRaises(ValueError):c.load_file(file)

    def test_restore_json_and_unread_never_clears(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'old.json';file.write_text('{"channel":196,"old_frequency_mhz":"435.3375"}')
            self.assertEqual(c.load_file(file),{196:'04353375'})
            file=Path(folder)/'snap.csv';file.write_text('channel,address,frequency_mhz,state\n000 (?),000,145.8000,stored\n2,002,,unread\n3,003,0.0000,empty\n')
            self.assertEqual(c.load_file(file),{0:'01458000',3:'00000000'})

    def test_duplicates_trunking_partial_and_clear(self):
        snapshot=inv();snapshot.records[22]=p.Channel(22,'04353750',b'F04353750\r')
        with self.assertRaises(ValueError):c.validate_plan(snapshot,{23:'04353750'})
        with self.assertRaises(ValueError):c.validate_plan(snapshot,{23:'04502250',24:'04502250'})
        self.assertEqual(c.validate_plan(snapshot,{22:'00000000'}),{22:'00000000'})
        snapshot.records[5]=p.Channel(5,'04502250',b'TN',True)
        with self.assertRaises(ValueError):c.validate_plan(snapshot,{5:'04353750'})
        snapshot.cancelled=True
        with self.assertRaises(ValueError):c.validate_plan(snapshot,{22:'00000000'})

    def test_compare_unknown_not_empty(self):
        result=c.compare({1:'00000000',2:'04353750',3:'04353750',5:'00000000'}, {1:'04353750',2:'00000000',3:'04502250',4:'04502250'})
        self.assertEqual([row[3] for row in result],['added','cleared','changed','unknown','unknown'])

    def test_preflight_aborts_all_writes(self):
        snapshot=inv()
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[snapshot.records[1],p.Channel(2,'04502250',b'changed')]),patch('programming.program_channel') as write:
            with self.assertRaises(p.ProgrammingError):c.apply_plan(None,snapshot,{1:'04353750',2:'04502250'},folder,Path(folder)/'log','COM5',19200,threading.Event(),lambda *a:None)
            write.assert_not_called()

    def test_batch_cancel_and_first_error_no_retry(self):
        for failure in (False,True):
            snapshot=inv();cancel=threading.Event()
            with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[snapshot.records[1],snapshot.records[2]]),patch('programming.program_channel',side_effect=OSError('lost') if failure else None,return_value=(p.Channel(1,'04353750',b'F04353750\r'),'backup')) as write:
                args=(None,snapshot,{1:'04353750',2:'04502250'},folder,Path(folder)/'log','COM5',19200,cancel,lambda *args:cancel.set())
                if failure:
                    with self.assertRaises(OSError):c.apply_plan(*args)
                else:self.assertEqual(c.apply_plan(*args),[1])
                self.assertEqual(write.call_count,1)

    def test_channel1000_and_zero_wire(self):
        old=p.Channel(0,'04353750',b'C000 F04353750 TF\r')
        new=p.Channel(0,'00000000',b'C000 F00000000 TF\r')
        from test_programming import FakePort
        with tempfile.TemporaryDirectory() as folder,patch('programming.read_channel',side_effect=[old,new]),patch('radio.capture',side_effect=[b'',new.raw]):
            port=FakePort();p.program_channel(port,old,'0',folder,Path(folder)/'log','COM5',19200)
            self.assertEqual(port.writes,[b'PM000 00000000\r'])
        with patch('radio.exchange',return_value=old.raw) as read:
            self.assertEqual(p.read_channel(None,1000,'log','COM5',19200),old)
            self.assertEqual(read.call_args.args[1],'PM000')

class SearchTests(unittest.TestCase):
    def test_bounds_and_commands(self):
        self.assertEqual(s.bounds('430','440'),('04300000','04400000'))
        for low,high in [('440','430'),('54','108'),('430.001','440')]:
            with self.assertRaises((ValueError,p.ProgrammingError)):s.bounds(low,high)
        with self.assertRaises(ValueError):s.exchange(None,'AC','log','COM5',19200)
        for raw in [b'NG\r',b'C001 F04353750 TN\r',b'F04353750',b'OK\r']:
            self.assertIsNone(s.observed_frequency(raw))

    def simulate(self,first,second=None,sq=b'+\r',known=None):
        stop=threading.Event();emitted=[];calls=[];counts={}
        def control(port,cmd,*args):
            calls.append(cmd)
            counts[cmd]=counts.get(cmd,0)+1
            if cmd=='LL':return b'LL04300000\r'
            if cmd=='LU':return b'LU04400000\r'
            return b'OK\r'
        reads=iter([b'MD02\r',first,sq]+([second,b'MD02\r'] if second is not None else []))
        def query(port,cmd,*args):
            if cmd=='MD' and stop.is_set():return b'MD01\r'
            value=next(reads)
            return value
        def wait(delay):stop.set();return True
        with tempfile.TemporaryDirectory() as folder,patch('frequency_search.exchange',side_effect=control),patch('radio.exchange',side_effect=query),patch.object(stop,'wait',side_effect=wait):
            s.run_search(None,'COM5',19200,'430','440',folder,Path(folder)/'log',stop,lambda *args:emitted.append(args),known)
            self.assertTrue(list((Path(folder)/'search-backups').glob('*.json')))
        self.assertEqual(calls[-1],'KEY01')
        return emitted

    def test_search_matching_frequency_and_membership(self):
        raw=b'F04353750\r'
        hits=self.simulate(raw,raw,known=set())
        self.assertEqual(hits[0][1][0],'04353750');self.assertEqual(hits[0][1][2],'new')
        self.assertEqual(self.simulate(raw,raw,known={'04353750'})[0][1][2],'known')

    def test_unknown_or_changing_frequency_not_logged(self):
        self.assertEqual(self.simulate(b'NG\r'),[])
        self.assertEqual(self.simulate(b'F04353750\r',b'F04355000\r'),[])
        self.assertEqual(self.simulate(b'F04353750\r',sq=b'-\r'),[])
        self.assertEqual(self.simulate(b'F04502250\r'),[])

    def test_bad_limits_fail_before_mutations(self):
        with tempfile.TemporaryDirectory() as folder,patch('frequency_search.exchange',return_value=b'NG\r') as ex:
            with self.assertRaises(ValueError):s.run_search(None,'COM5',19200,'430','440',folder,Path(folder)/'log',threading.Event(),lambda *args:None,None)
            self.assertEqual([x.args[1] for x in ex.call_args_list],['LL','LU'])

class NewUITests(unittest.TestCase):
    def test_editor_stages_import_without_serial_and_search_translates(self):
        import tkinter as tk
        import window
        from channel_editor import ChannelEditor
        root=tk.Tk();root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder,patch.object(window.App,'refresh'):
                app=window.App(root,Path(folder));app.programming.inventory=inv();app.port.set('COM5');app.baud.set('19200')
                editor=ChannelEditor(app);editor.top.withdraw()
                file=Path(folder)/'x.csv';file.write_text('channel,frequency_mhz\n1000,435.375\n')
                with patch('channel_editor.filedialog.askopenfilename',return_value=str(file)),patch('channel_editor.simpledialog.askinteger',return_value=1),patch.object(app.programming,'launch') as launch:
                    editor.import_csv();self.assertEqual(editor.changes,{0:'04353750'});launch.assert_not_called()
                app.language_ui.language='en';app.language_ui.apply()
                self.assertEqual(app.notebook.tab(app.search.frame,'text'),'Frequency search')
                editor.top.destroy()
        finally:root.destroy()

if __name__=='__main__':unittest.main()
