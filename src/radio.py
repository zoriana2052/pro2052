"""PRO-2052: query-only diagnostics and rechecked activity observations."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys
import time

FIELDS = ['utc', 'local', 'event', 'port', 'baud', 'query', 'raw_hex',
          'raw_ascii', 'frequency_mhz', 'source', 'note']
ALLOWED = {'MD', 'MA', 'SQ'}


def wire(query):
    if query not in ALLOWED and not re.fullmatch(r'PM[0-9]{3}', query):
        raise ValueError('Only MD, MA, SQ and PM000..PM999 queries allowed')
    return query.encode('ascii') + b'\r'


def record(path, **values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    row = dict.fromkeys(FIELDS, '')
    row.update(utc=now.isoformat(timespec='milliseconds'),
               local=now.astimezone().isoformat(timespec='milliseconds'))
    row.update(values)
    exists = path.exists() and path.stat().st_size > 0
    with path.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def capture(port, seconds, stop_at_cr=False):
    deadline = time.monotonic() + seconds
    data = bytearray()
    while time.monotonic() < deadline and len(data) < 65536:
        data.extend(port.read(1 if stop_at_cr else min(port.in_waiting or 1, 65536 - len(data))))
        if stop_at_cr and data.endswith(b'\r'):
            break
    return bytes(data)


def exchange(port, query, path, name, baud):
    payload = wire(query)  # Validate before ANY write.
    stale = capture(port, 0.2)
    if stale:
        record(path, event='unattributed_rx', port=name, baud=baud,
               raw_hex=stale.hex(), raw_ascii=repr(stale), source='serial')
    port.write(payload)
    data = capture(port, 1.5, stop_at_cr=True)
    record(path, event='query_rx' if data else 'timeout', port=name, baud=baud,
           query=query, raw_hex=data.hex(), raw_ascii=repr(data), source='serial',
           note='Receive window; response association not guaranteed; not a transmission event')
    print(f'{query}: {data!r}' if data else f'{query}: TIMEOUT (no response)')
    return data


def channel_info(data):
    # Scaling checked against the user's display: F04676625 = 467.6625 MHz.
    match = re.fullmatch(rb'C([0-9]{3}) F([0-9]{8}) TF(?: [A-Z0-9]+)*\r', data)
    if not match:
        return None
    return match[1].decode('ascii'), format(Decimal(int(match[2])) / 10000, '.4f')


def poll_once(port, queries, path, name, baud, activity=False):
    mode = None  # Never reuse the previous cycle's mode.
    responses = {}
    for query in queries:
        data = exchange(port, query, path, name, baud)
        responses[query] = data
        response = data.strip()
        if query == 'MD':
            mode = response
        if query == 'MA' and mode == b'MD00' and response == b'NG':
            print('MA unavailable during SCAN; checking SQ next. No frequency inferred.')
            continue
        if not data:
            print('Stopped: no response. Check REMOTE, baud, connection and raw log.')
            return False
        if not data.endswith(b'\r'):
            print('Stopped: incomplete response; see raw log.')
            return False
        tokens = re.split(rb'[\s]+', response)
        if any(x in tokens for x in (b'NG', b'ERR', b'ORER')):
            print(f'Stopped: scanner rejected {query}: {response!r}. See raw log.')
            return False
        if response == query.encode('ascii'):
            print(f'Stopped: echo only for {query}; scanner response not verified.')
            return False
    first = channel_info(responses.get('MA', b''))
    if activity and mode in (b'MD00', b'MD01') and first and responses.get('SQ') == b'+\r':
        second = exchange(port, 'MA', path, name, baud)
        if not second or not second.endswith(b'\r') or second.strip() in (b'ERR', b'ORER', b'MA'):
            print('Stopped: recheck failed; see raw log.')
            return False
        if channel_info(second) == first:
            channel, mhz = first
            record(path, event='activity_observation', port=name, baud=baud,
                   frequency_mhz=mhz, source='MA-SQ-MA',
                   note=f'Channel {channel}; matching conventional channel/frequency around SQ+. '
                        'Sequential samples, not proof of continuous reception or a call start.')
            print(f'ACTIVITY observation: channel {channel}, {mhz} MHz')
        else:
            print('Channel unavailable or changed on recheck; no activity frequency recorded.')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', default='logs/observations.csv')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('ports', help='List serial ports without opening them')
    for name in ('diagnose', 'probe', 'observe'):
        p = sub.add_parser(name)
        p.add_argument('--port', required=True)
        p.add_argument('--baud', type=int, choices=[2400, 4800, 9600, 19200], default=9600)
        if name == 'probe':
            p.add_argument('--channel', type=int, choices=range(1000), metavar='0..999')
        if name == 'observe':
            p.add_argument('--samples', type=int, default=10)
    p = sub.add_parser('note', help='Manual observation, never an automatic detection')
    p.add_argument('--mhz', required=True)
    p.add_argument('--text', default='')
    args = parser.parse_args()
    if args.action == 'note':
        try:
            frequency = Decimal(args.mhz)
            if not frequency.is_finite() or frequency <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            parser.error('--mhz must be a positive finite number (decimal point)')
        record(args.log, event='manual_observation', frequency_mhz=str(frequency),
               source='user', note=args.text)
        print(f'Saved manual observation: {args.log}')
        return 0
    if args.action == 'observe' and not 1 <= args.samples <= 1000:
        parser.error('--samples must be 1..1000')
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print('Install dependencies: python -m pip install -r requirements.txt', file=sys.stderr)
        return 2
    if args.action == 'ports':
        ports = list(list_ports.comports())
        for p in ports:
            print(f'{p.device}: {p.description} | {p.hwid}')
        if not ports:
            print('No serial ports. Check USB adapter and its manufacturer driver.')
        return 0
    from platform_support import valid_port
    if not valid_port(args.port):
        parser.error('Select a serial port: COM3 on Windows or /dev/cu.usbserial-… on macOS')
    try:
        with serial.Serial(port=None, baudrate=args.baud, bytesize=8, parity='N',
                           stopbits=1, timeout=0.1, write_timeout=1,
                           xonxoff=False, rtscts=False, dsrdtr=False) as port:
            port.dtr = False
            port.rts = False
            port.port = args.port
            port.open()
            print(f'Opened {args.port}: {args.baud} 8N1, no flow control')
            if args.action == 'diagnose':
                print('Port opened and closed without sending bytes. Scanner link not yet verified.')
                return 0
            queries = ['MD', 'MA', 'SQ']
            if args.action == 'probe' and args.channel is not None:
                queries.append(f'PM{args.channel:03d}')
            for _ in range(args.samples if args.action == 'observe' else 1):
                if not poll_once(port, queries, args.log, args.port, args.baud,
                                 activity=args.action == 'observe'):
                    return 1
                if args.action == 'observe':
                    time.sleep(1)
    except (serial.SerialException, OSError) as exc:
        print(f'COM/log error: {exc}\nCheck port number, driver and cable; close other serial apps.', file=sys.stderr)
        return 1
    print(f'Observations saved: {args.log}. Timestamps are PC observations, not call boundaries.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nStopped; completed CSV rows retained.')
        sys.exit(130)
