import csv
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import patch
import window

class FakePort:
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def open(self): pass

class WorkerTests(unittest.TestCase):
    def test_rows_stop_and_close(self):
        path = Path('gui-test.csv')
        events, stop, port = queue.Queue(), threading.Event(), FakePort()
        def poll(*args, **kwargs):
            window.radio.record(path, event='activity_observation', frequency_mhz='450.2250', note='Channel 022')
            stop.set()
            return True
        try:
            with patch.dict(sys.modules, {'serial': types.SimpleNamespace(Serial=lambda **kw: port)}), patch('window.radio.poll_once', side_effect=poll):
                window.monitor('COM5',19200,path,stop,events)
            received = list(events.queue)
            self.assertEqual(sum(k=='row' and r['event']=='activity_observation' for k,r in received),1)
            self.assertEqual(received[-1],('done',None))
            self.assertTrue(port.closed)
        finally:
            path.unlink(missing_ok=True)

    def test_open_failure_reports_error_and_done(self):
        def fail(**kwargs): raise OSError('port busy')
        events = queue.Queue()
        with patch.dict(sys.modules, {'serial': types.SimpleNamespace(Serial=fail)}):
            window.monitor('COM5',19200,Path('unused.csv'),threading.Event(),events)
        self.assertEqual([k for k,v in events.queue],['error','done'])

    def test_window_populates_table(self):
        root = window.tk.Tk()
        root.withdraw()
        try:
            with patch.object(window.App,'refresh'):
                app = window.App(root)
            app.events.put(('row',dict(event='activity_observation',local='2026-10-26T06:30:39-04:00',note='Channel 022',frequency_mhz='450.2250')))
            app.drain()
            root.update_idletasks()
            self.assertEqual(app.count,1)
            self.assertEqual(app.tree.item(app.tree.get_children()[0])['values'][-1],'450.2250')
        finally:
            root.destroy()

if __name__=='__main__': unittest.main()
