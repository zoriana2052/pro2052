"""Single-channel programming; isolated from radio.py's read-only command allowlist.
Manual pp.48,49,52,68: https://www.rigpix.com/rs-realistic/radioshack_pro2052_manual.pdf
Physical channel 1000 uses address 000, confirmed by the user on this scanner.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import os
import re
import uuid
import radio

class ProgrammingError(Exception):
    def __init__(self, code, detail=''):
        self.code, self.detail = code, detail
        super().__init__(code + (': ' + detail if detail else ''))

# Inclusive endpoints and channel spacing from the manufacturer's specifications.
BANDS = [('29','54','.005'), ('108','136.975','.0125'),
         ('137','174','.005'), ('179.75','215.75','6'),
         ('216','224.995','.005'), ('225','512','.0125'),
         ('806','823.9375','.0125'), ('851','868.9875','.0125'),
         ('896.1125','956','.0125'), ('1240','1300','.0125')]

def channel_number(value):
    if not re.fullmatch(r'[0-9]{1,4}', str(value)) or not 1 <= int(value) <= 1000:
        raise ProgrammingError('channel')
    return int(value) % 1000

def frequency_digits(value):
    value = str(value).strip().replace(',', '.')
    if not re.fullmatch(r'[0-9]{1,4}(?:\.[0-9]{1,4})?', value):
        raise ProgrammingError('frequency')
    try:
        freq = Decimal(value)
    except InvalidOperation:
        raise ProgrammingError('frequency')
    for low, high, step in BANDS:
        low, high, step = map(Decimal, (low, high, step))
        if low <= freq <= high:
            if (freq-low) % step:
                raise ProgrammingError('step', str(step * 1000) + ' kHz')
            return f'{int(freq * 10000):08d}'
    raise ProgrammingError('band')

def mhz(digits):
    return format(Decimal(int(digits)) / 10000, '.4f')

@dataclass(frozen=True)
class Channel:
    number: int
    digits: str
    raw: bytes
    trunked: bool = False


def parse_channel(raw, number):
    # PM replies must contain a frequency. Never accept command echo or OK as data.
    match = re.fullmatch(rb'(?:C([0-9]{3}) )?F([0-9]{8})(?: (T[FN])(?: [A-Z0-9]+)*)?\r', raw)
    if not match or (match[1] and int(match[1]) != number):
        raise ProgrammingError('response', repr(raw))
    return Channel(number, match[2].decode('ascii'), raw, match[3] == b'TN')


def read_channel(port, number, log, name, baud):
    number = channel_number(number)
    return parse_channel(radio.exchange(port, f'PM{number:03d}', log, name, baud), number)


def program_channel(port, expected, frequency, data_dir, log, name, baud):
    number = channel_number(expected.number or 1000)
    from channel_tools import digits as target_digits
    digits = target_digits(frequency)
    if expected.trunked:
        raise ProgrammingError('trunked')
    if digits == expected.digits:
        raise ProgrammingError('same')
    # Check again after user confirmation; do not overwrite a changed channel.
    current = read_channel(port, number or 1000, log, name, baud)
    if current != expected:
        raise ProgrammingError('changed')
    backup_dir = Path(data_dir) / 'channel-backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f'channel-{number:03d}-{uuid.uuid4().hex}.json'
    content = dict(utc=datetime.now(timezone.utc).isoformat(), port=name, baud=baud,
                   channel=number, old_frequency_mhz=mhz(current.digits),
                   new_frequency_mhz=mhz(digits), old_raw_hex=current.raw.hex(),
                   scope='One channel frequency; not a complete scanner backup')
    # A backup failure aborts before any programming command is sent.
    with backup.open('x', encoding='utf-8') as file:
        json.dump(content, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    command = f'PM{number:03d} {digits}'
    radio.record(log, event='program_intent', port=name, baud=baud, query=command,
                 source='channel-editor', note=str(backup))
    stale = radio.capture(port, .2)
    if stale:
        raise ProgrammingError('stale', repr(stale))
    # Only this validated, explicitly confirmed path can emit a write command.
    try:
        payload = command.encode('ascii') + b'\r'
        if port.write(payload) != len(payload):
            raise ProgrammingError('uncertain')
        reply = radio.capture(port, 1.5, stop_at_cr=True)
        radio.record(log, event='program_reply', port=name, baud=baud, query=command,
                     raw_hex=reply.hex(), raw_ascii=repr(reply), source='channel-editor')
        actual = read_channel(port, number or 1000, log, name, baud)
        # Hardware also returns the new channel record instead of OK (observed C198).
        acknowledged = reply == b'OK\r'
        if not acknowledged:
            try:
                returned = parse_channel(reply, number)
                acknowledged = returned.digits == digits and not returned.trunked
            except ProgrammingError:
                pass
        if not acknowledged or actual.digits != digits or actual.trunked:
            raise ProgrammingError('uncertain', f'ACK={reply!r}; readback={mhz(actual.digits)} MHz')
        radio.record(log, event='program_verified', port=name, baud=baud,
                     frequency_mhz=mhz(digits), source='channel-editor', note=f'Channel {number:03d}; backup={backup}')
        return actual, backup
    except Exception as exc:
        if isinstance(exc, ProgrammingError) and exc.code == 'uncertain':
            raise
        raise ProgrammingError('uncertain', str(exc)) from exc
