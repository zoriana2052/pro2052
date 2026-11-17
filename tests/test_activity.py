import unittest
from unittest.mock import patch
import radio

CHANNEL = b'C049 F04676625 TF DF LF AF RF N00\r'


class ActivityTests(unittest.TestCase):
    def test_cr_returns_without_waiting_and_preserves_next_frame(self):
        class Port:
            data = bytearray(b'MD00\r+\r')
            def read(self, size):
                result = bytes(self.data[:size])
                del self.data[:size]
                return result
        port = Port()
        self.assertEqual(radio.capture(port, 1.5, True), b'MD00\r')
        self.assertEqual(bytes(port.data), b'+\r')

    def test_matching_recheck_records_frequency(self):
        with patch('radio.exchange', side_effect=[b'MD00\r', CHANNEL, b'+\r', CHANNEL]), patch('radio.record') as record:
            self.assertTrue(radio.poll_once(None, ['MD', 'MA', 'SQ'], '', 'COM5', 19200, True))
            self.assertEqual(record.call_args.kwargs['frequency_mhz'], '467.6625')
            self.assertEqual(record.call_args.kwargs['event'], 'activity_observation')

    def test_uncertain_frequency_is_not_recorded(self):
        cases = [[b'MD00\r', b'NG\r', b'+\r'],
                 [b'MD00\r', CHANNEL, b'-\r'],
                 [b'MD00\r', CHANNEL, b'+\r', b'NG\r'],
                 [b'MD00\r', CHANNEL, b'+\r', CHANNEL.replace(b'C049', b'C050')]]
        for replies in cases:
            with self.subTest(replies=replies), patch('radio.exchange', side_effect=replies), patch('radio.record') as record:
                self.assertTrue(radio.poll_once(None, ['MD', 'MA', 'SQ'], '', 'COM5', 19200, True))
                record.assert_not_called()

    def test_partial_response_stops(self):
        with patch('radio.exchange', return_value=b'MD00'):
            self.assertFalse(radio.poll_once(None, ['MD', 'MA', 'SQ'], '', 'COM5', 19200))


if __name__ == '__main__':
    unittest.main()
