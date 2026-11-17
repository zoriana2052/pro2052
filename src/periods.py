"""Conservative display grouping; raw observations remain untouched."""
from dataclasses import dataclass
from datetime import datetime
import re
import radio

@dataclass
class Period:
    channel: str
    frequency: str
    first: str
    last: str
    timestamp: datetime
    count: int = 1

class Periods:
    def __init__(self, max_gap=5.0):
        self.max_gap = max_gap
        self.current = None
        self.mode = None

    def close(self):
        self.current = None

    def feed(self, row):
        event = row.get('event', '')
        if event in ('session_start', 'timeout', 'unattributed_rx'):
            self.close()
            return None
        if event == 'query_rx':
            try:
                raw = bytes.fromhex(row.get('raw_hex', ''))
            except ValueError:
                self.close()
                return None
            query = row.get('query')
            if query == 'MD':
                if raw != self.mode:
                    self.close()
                self.mode = raw
            elif query == 'SQ' and raw != b'+\r':
                self.close()
            elif query == 'MA':
                info = radio.channel_info(raw)
                if info is None or (self.current and info != (self.current.channel, self.current.frequency)):
                    self.close()
            return None
        if event != 'activity_observation':
            return None
        match = re.search(r'Channel ([0-9]{3})', row.get('note',''))
        stamp = row.get('local','')
        try:
            timestamp = datetime.fromisoformat(row.get('utc') or stamp)
            if timestamp.tzinfo is None or not match or not row.get('frequency_mhz'):
                raise ValueError('Missing observation information')
        except (TypeError, ValueError):
            self.close()
            return None
        channel, frequency = match[1], row['frequency_mhz']
        previous = self.current
        gap = (timestamp - previous.timestamp).total_seconds() if previous else None
        new = not (previous and (channel,frequency)==(previous.channel,previous.frequency)
                   and 0 <= gap <= self.max_gap)
        if new:
            self.current = Period(channel,frequency,stamp,stamp,timestamp)
        else:
            self.current.last = stamp
            self.current.timestamp = timestamp
            self.current.count += 1
        return self.current, new
