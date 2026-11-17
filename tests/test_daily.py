import csv
from pathlib import Path
import tempfile
import unittest
import tkinter as tk
from unittest.mock import patch
import radio, history, window
from frequency_names import FrequencyNames

class DailyTests(unittest.TestCase):
    def test_midnight_counts_filters_and_read_only(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'log.csv'
            rows=[]
            def observation(stamp):
                return dict(event='activity_observation',local=stamp,utc=stamp,frequency_mhz='450.2250',note='Channel 022')
            rows=[observation('2026-10-26T23:59:59-04:00'),observation('2026-10-27T00:00:01-04:00'),observation('2026-10-27T00:00:03-04:00'),dict(event='query_rx',query='SQ',raw_hex='2d0d'),observation('2026-10-27T00:00:05-04:00')]
            with path.open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=radio.FIELDS)
                writer.writeheader(); writer.writerows(rows)
            original=path.read_bytes()
            totals=[]
            groups,skipped,count=history.load_history(path,daily=totals)
            self.assertEqual((len(groups),skipped,count),(2,0,5))
            self.assertEqual([(r['day'],r['samples'],r['periods']) for r in totals],[('2026-10-26',1,1),('2026-10-27',3,2)])
            self.assertEqual(totals[1]['first'],'2026-10-27T00:00:01-04:00')
            self.assertEqual(totals[1]['last'],'2026-10-27T00:00:05-04:00')
            names=FrequencyNames(Path(folder)/'names.json')
            names.save('450.225','Test')
            self.assertEqual(len(history.filter_daily(totals,names,'450,22','TEST','2026-10-27')),1)
            self.assertEqual(history.filter_daily(totals,names,by_periods=True)[0]['periods'],2)
            self.assertEqual(path.read_bytes(),original)

    def test_summary_view_and_return(self):
        root=tk.Tk(); root.withdraw()
        try:
            with patch.object(window.App,'refresh'):
                app=window.App(root)
            view=history.HistoryWindow(app); view.top.withdraw()
            view.daily=[dict(day='2026-10-26',frequency='450.2250',first='first',last='last',samples=12,periods=3)]
            view.view.current(1); view.apply()
            self.assertEqual(len(view.tree.get_children()),1)
            item=view.tree.get_children()[0]
            self.assertEqual(view.tree.set(item,'periods'),'3')
            view.view.current(0); view.apply()
            self.assertEqual(len(view.tree.get_children()),0)
            view.close()
        finally: root.destroy()

if __name__=='__main__': unittest.main()
