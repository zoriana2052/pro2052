import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk
import history
import radio
import window
from frequency_names import FrequencyNames

class HistoryTests(unittest.TestCase):
    def test_read_group_filter_preserve(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'log.csv'
            def sample(second):
                return dict(event='activity_observation',utc=f'2026-10-26T10:00:{second:02d}+00:00',local=f'2026-10-26T06:00:{second:02d}-04:00',frequency_mhz='450.2250',note='Channel 022')
            with path.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=radio.FIELDS)
                w.writeheader()
                w.writerow(sample(0)); w.writerow(sample(2))
                w.writerow(dict(event='query_rx',query='SQ',raw_hex='2d0d'))
                w.writerow(sample(4))
                w.writerow(dict(event='activity_observation',local='broken'))
            original=path.read_bytes()
            groups,skipped,rows=history.load_history(path)
            self.assertEqual([p.count for p in groups],[2,1])
            self.assertEqual((skipped,rows),(1,5))
            names=FrequencyNames(Path(folder)/'names.json')
            names.save('450.225','Мій канал')
            self.assertEqual(len(history.filter_periods(groups,names,'450,225','МІЙ','2026-10-26')),2)
            self.assertEqual(history.filter_periods(groups,names,day='2026-10-27'),[])
            with self.assertRaises(ValueError): history.filter_periods(groups,names,day='bad')
            self.assertEqual(path.read_bytes(),original)

    def test_raw_only_and_wrong_format(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'log.csv'
            with path.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=radio.FIELDS); w.writeheader()
                w.writerow(dict(event='query_rx',query='MA',raw_hex=b'C022 F04502250 TF\r'.hex()))
            self.assertEqual(history.load_history(path)[0],[])
            path.write_text('a,b\n1,2\n')
            with self.assertRaises(ValueError): history.load_history(path)

    def test_viewer_does_not_open_serial(self):
        root=tk.Tk(); root.withdraw()
        try:
            with patch.object(window.App,'refresh'),patch('window.monitor') as monitor:
                app=window.App(root)
                viewer=history.HistoryWindow(app)
                viewer.top.withdraw()
                viewer.apply(); viewer.reset()
                root.update_idletasks()
                monitor.assert_not_called()
                self.assertEqual(len(viewer.tree.get_children()),0)
                viewer.close()
        finally: root.destroy()

if __name__=='__main__': unittest.main()
