import unittest
from periods import Periods

def sample(second, channel='022', frequency='450.2250'):
    return dict(event='activity_observation',local=f'2026-10-26T06:30:{second:02d}-04:00',
                note=f'Channel {channel}',frequency_mhz=frequency)

def raw(query, response):
    return dict(event='query_rx',query=query,raw_hex=response.hex())

class PeriodTests(unittest.TestCase):
    def test_repeats_update_last_count_not_first(self):
        p = Periods()
        first,new = p.feed(sample(0))
        second,new = p.feed(sample(2))
        self.assertIs(first,second)
        self.assertFalse(new)
        self.assertEqual(second.count,2)
        self.assertEqual(second.first,sample(0)['local'])
        self.assertEqual(second.last,sample(2)['local'])

    def test_silence_ng_timeout_and_gap_split(self):
        for boundary in [raw('SQ',b'-\r'),raw('MA',b'NG\r'),dict(event='timeout'),dict(event='unattributed_rx')]:
            with self.subTest(boundary=boundary):
                p = Periods()
                p.feed(sample(0))
                p.feed(boundary)
                period,new = p.feed(sample(2))
                self.assertTrue(new)
                self.assertEqual(period.count,1)
        p = Periods()
        p.feed(sample(0))
        self.assertTrue(p.feed(sample(6))[1])

    def test_change_and_return_split(self):
        p = Periods()
        p.feed(sample(0))
        p.feed(raw('MA',b'C023 F04603250 TF\r'))
        self.assertTrue(p.feed(sample(2))[1])
        self.assertTrue(p.feed(sample(3,'023','460.3250'))[1])

    def test_positive_queries_do_not_split(self):
        p = Periods()
        p.feed(raw('MD',b'MD00\r'))
        p.feed(sample(0))
        for row in [raw('MD',b'MD00\r'),raw('MA',b'C022 F04502250 TF\r'),raw('SQ',b'+\r')]:
            p.feed(row)
        self.assertFalse(p.feed(sample(2))[1])
        p.close()
        self.assertTrue(p.feed(sample(3))[1])

if __name__ == '__main__': unittest.main()
