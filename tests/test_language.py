import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import tkinter as tk
import window
from ui_language import translate

class LanguageTests(unittest.TestCase):
    def test_switch_preserves_fast_mode_and_live_status(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(window.App, 'refresh'):
                app = window.App(root)
            with tempfile.TemporaryDirectory(dir='.') as folder:
                app.language_ui.path = Path(folder)/'settings.json'
                app.pace.set('Швидше')
                app.language_ui.choice.set('English')
                app.language_ui.changed()
                self.assertEqual(app.start_button.cget('text'),'Start')
                self.assertEqual(app.pace.get(),'Faster')
                self.assertEqual(window.POLL_DELAYS[app.pace.get()],0.25)
                app.status.set('Шумоподавлювач відкритий. Спостерігаємо…')
                self.assertEqual(app.status.get(),'Squelch open. Monitoring…')
                app.summary.set('Спостережень: 17 • У таблиці останні 1000, у CSV — усі')
                self.assertTrue(app.summary.get().startswith('Observations: 17'))
                self.assertIn('"en"',app.language_ui.path.read_text())
                app.language_ui.choice.set('Українська')
                app.language_ui.changed()
                self.assertEqual(app.pace.get(),'Швидше')
                self.assertEqual(app.start_button.cget('text'),'Почати')
                self.assertEqual(app.summary.get(),'Спостережень: 17 • У таблиці останні 1000, у CSV — усі')
                root.update_idletasks()
        finally:
            root.destroy()

    def test_paths_and_raw_protocol_are_unchanged(self):
        for value in ('C:/logs/activity.csv', "SQ: b'+\\r'", '450.2250'):
            self.assertEqual(translate(value,'en'),value)

if __name__ == '__main__': unittest.main()
