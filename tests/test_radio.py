import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import radio


class SafetyTests(unittest.TestCase):
    def test_scan_ng_continues_to_sq_and_next_cycle(self):
        with patch('radio.exchange', side_effect=[b'MD00\r', b'NG\r', b'-\r'] * 2) as exchange:
            for _ in range(2):
                self.assertTrue(radio.poll_once(None, ['MD', 'MA', 'SQ'], '', 'COM5', 19200))
            self.assertEqual([call.args[1] for call in exchange.call_args_list],
                             ['MD', 'MA', 'SQ'] * 2)

    def test_other_errors_still_stop(self):
        for replies in ([b'MD01\r', b'NG\r'], [b'MD00\r', b'ERR\r'],
                        [b'MD00\r', b'ORER\r'], [b'MD00\r', b''], [b'MD\r']):
            with self.subTest(replies=replies), patch('radio.exchange', side_effect=replies):
                self.assertFalse(radio.poll_once(None, ['MD', 'MA', 'SQ'], '', 'COM5', 19200))

    def test_allowlist(self):
        for q in ['AC', 'KEY00', 'MA001', 'PM001 14500000', 'MD\rAC', 'QUN', 'RF14500000']:
            with self.assertRaises(ValueError):
                radio.wire(q)
        for q in ['MD', 'MA', 'SQ', 'PM000', 'PM999']:
            self.assertEqual(radio.wire(q), q.encode() + b'\r')

    def test_csv_has_no_inferred_frequency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log.csv'
            class Port:
                def write(self, data):
                    self.sent = data
            port = Port()
            with patch('radio.capture', side_effect=[b'', b'F00145000\r']):
                radio.exchange(port, 'MA', path, 'COM3', 9600)
            with path.open(encoding='utf-8') as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row['frequency_mhz'], '')
            self.assertTrue(row['utc'].endswith('+00:00'))
            self.assertEqual(port.sent, b'MA\r')

    def test_timeout_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log.csv'
            with patch('radio.capture', return_value=b''):
                from unittest.mock import Mock
                self.assertEqual(radio.exchange(Mock(), 'SQ', path, 'COM3', 9600), b'')
            with path.open(encoding='utf-8') as f:
                self.assertEqual(next(csv.DictReader(f))['event'], 'timeout')


if __name__ == '__main__':
    unittest.main()
