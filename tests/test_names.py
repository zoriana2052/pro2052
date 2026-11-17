from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import tkinter as tk
import window
from frequency_names import FrequencyNames

class NamesTests(unittest.TestCase):
    def test_persistence_and_removal(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path = Path(folder)/'names.json'
            names = FrequencyNames(path)
            names.save('450.2250','Мій канал')
            self.assertEqual(FrequencyNames(path).get('450.225'),'Мій канал')
            names.save('450.225','')
            self.assertEqual(FrequencyNames(path).get('450.2250'),'')

    def test_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory(dir='.') as folder:
            path=Path(folder)/'names.json'
            path.write_text('broken',encoding='utf-8')
            names=FrequencyNames(path)
            with self.assertRaises(ValueError): names.save('450.225','test')
            self.assertEqual(path.read_text(),'broken')

    def test_update_matching_rows_and_cancel(self):
        root=tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory(dir='.') as folder, patch.object(window.App,'refresh'):
                app=window.App(root)
                app.names=FrequencyNames(Path(folder)/'names.json')
                a=app.tree.insert('',0,values=('first','last','022',1,'','450.2250'))
                b=app.tree.insert('',0,values=('first','last','022',1,'','450.2250'))
                c=app.tree.insert('',0,values=('first','last','023',1,'','460.3250'))
                app.tree.selection_set(a)
                with patch('window.ask_name',return_value='My frequency'):
                    app.edit_frequency_name()
                self.assertEqual(app.tree.set(a,'name'),'My frequency')
                self.assertEqual(app.tree.set(b,'name'),'My frequency')
                self.assertEqual(app.tree.set(c,'name'),'')
                with patch('window.ask_name',return_value=None): app.edit_frequency_name()
                self.assertEqual(app.names.get('450.225'),'My frequency')
                app.language_ui.language='en'
                app.language_ui.apply()
                self.assertEqual(app.tree.heading('name')['text'],'Name')
                self.assertEqual(app.tree.set(a,'name'),'My frequency')
        finally:
            root.destroy()

if __name__=='__main__': unittest.main()
