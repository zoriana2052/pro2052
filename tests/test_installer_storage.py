import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app_storage import data_folder, import_legacy_data, VERSION

class InstallerStorageTests(unittest.TestCase):
    def test_user_data_is_outside_program_directory(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': 'C:/Users/Test/AppData/Local'}, clear=True):
            self.assertEqual(data_folder(), Path('C:/Users/Test/AppData/Local/PRO2052'))
        self.assertEqual(VERSION, '1.0.0')

    def test_override_for_isolated_tests(self):
        with patch.dict(os.environ, {'PRO2052_DATA_DIR': 'isolated-data'}):
            self.assertEqual(data_folder(), Path('isolated-data').resolve())

    def test_import_recovers_all_data_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source=root/'old'/'data'; dest=root/'new'
            for name in ('logs', 'channel-backups', 'channel-inventories', 'search-backups'):
                (source/name).mkdir(parents=True)
                (source/name/'example.csv').write_text(name)
            (source/'connection.json').write_text('old')
            (source/'instance.lock').write_text('do not copy')
            dest.mkdir(); (dest/'connection.json').write_text('current')
            self.assertEqual(import_legacy_data(root/'old', dest), 4)
            self.assertEqual((dest/'connection.json').read_text(), 'current')
            self.assertFalse((dest/'instance.lock').exists())
            self.assertEqual(import_legacy_data(source, dest), 0)
            self.assertTrue((source/'logs'/'example.csv').exists())

    def test_same_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): import_legacy_data(tmp, tmp)
