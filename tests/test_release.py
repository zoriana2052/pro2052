import json
from pathlib import Path
import queue
import tempfile
import threading
import types
import sys
import unittest
from unittest.mock import patch
from app_storage import prepare_data, load_connection, atomic_json
from launcher import InstanceLock
import window

class ReleaseTests(unittest.TestCase):
    def test_migration_never_overwrites(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            base=Path(folder); old=base/'old'; data=base/'data'
            (old/'logs').mkdir(parents=True); (old/'logs'/'a.csv').write_text('original')
            (old/'frequency-names.json').write_text('{"450.225":"old"}')
            prepare_data(data,old)
            self.assertEqual((data/'logs'/'a.csv').read_text(),'original')
            (data/'frequency-names.json').write_text('{"450.225":"new"}')
            prepare_data(data,old)
            self.assertIn('new',(data/'frequency-names.json').read_text())
            self.assertIn('old',(old/'frequency-names.json').read_text())

    def test_settings_validation_and_restore(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'connection.json'
            atomic_json(path,{'port':'COM9','baud':'19200','pace':'fast'})
            self.assertEqual(load_connection(path),{'port':'COM9','baud':'19200','pace':'fast'})
            path.write_text('{bad')
            self.assertEqual(load_connection(path)['port'],'COM5')

    def test_lock_released_for_restart(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'lock'
            lock=InstanceLock(path)
            with self.assertRaises(RuntimeError): InstanceLock(path)
            lock.close()
            InstanceLock(path).close()

    def test_reconnect_after_failure_and_repeat_cycles(self):
        class Port:
            def __enter__(self): return self
            def __exit__(self,*args): self.closed=True
            def open(self): pass
        with tempfile.TemporaryDirectory(dir='.') as folder:
            events=queue.Queue(); stop=threading.Event(); port=Port(); count=0
            def poll(*args,**kwargs):
                nonlocal count
                count+=1
                window.radio.record(args[2],event='activity_observation',frequency_mhz='450.2250',note='Channel 022')
                if count==500: stop.set()
                return True
            with patch.dict(sys.modules,{'serial':types.SimpleNamespace(Serial=lambda **kw:port)}), patch('window.radio.poll_once',side_effect=OSError('adapter removed')):
                window.monitor('COM5',19200,Path(folder)/'failed.csv',stop,events,0)
            self.assertTrue(port.closed)
            self.assertIn('error',[k for k,v in events.queue])
            events=queue.Queue()
            with patch.dict(sys.modules,{'serial':types.SimpleNamespace(Serial=lambda **kw:port)}), patch('window.radio.poll_once',side_effect=poll):
                window.monitor('COM5',19200,Path(folder)/'second.csv',stop,events,0)
            self.assertEqual(sum(k=='row' and v['event']=='activity_observation' for k,v in events.queue),500)
            self.assertTrue(port.closed)

if __name__=='__main__': unittest.main()
