"""Read-only inventory of every three-digit PM address; physical 1000 needs mapping confirmation."""
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid
import radio
import programming as p

@dataclass
class Inventory:
    port: str
    baud: int
    confirmed_last: bool = False
    records: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    cancelled: bool = False
    started: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    path: str = ''

    @property
    def complete(self):
        return (len(self.records)==1000 and not self.errors and not self.cancelled and self.confirmed_last)

    def duplicates(self, digits, exclude=None):
        if digits=='00000000': return []
        return [address for address,ch in sorted(self.records.items()) if address!=exclude and ch.digits==digits]

    def label(self,address):
        return ('1000' if self.confirmed_last else '000 (?)') if address==0 else f'{address:03d}'


def read_address(port,address,log,name,baud):
    if not 0 <= address <= 999: raise ValueError('Invalid address')
    raw=radio.exchange(port,f'PM{address:03d}',log,name,baud)
    return p.parse_channel(raw,address)


def verify_last_channel(port,log,name,baud):
    # User explicitly selects physical channel 1000 on the front panel before this action.
    if radio.exchange(port,'MD',log,name,baud) != b'MD01\r':
        raise p.ProgrammingError('mapping')
    raw=radio.exchange(port,'MA',log,name,baud)
    manual=p.parse_channel(raw,0)
    stored=read_address(port,0,log,name,baud)
    if manual!=stored: raise p.ProgrammingError('mapping')
    return stored


def save_inventory(inventory, data_dir):
    folder=Path(data_dir)/'channel-inventories'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'channels-{uuid.uuid4().hex}.csv'
    with path.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['channel','address','frequency_mhz','type','state','duplicates','error','raw_hex','port','baud','snapshot_started_utc','complete'])
        for address in [*range(1,1000),0]:
            ch=inventory.records.get(address)
            others=inventory.duplicates(ch.digits,address) if ch else []
            state=('empty' if ch.digits=='00000000' else 'stored') if ch else 'unread'
            writer.writerow([inventory.label(address),f'{address:03d}',p.mhz(ch.digits) if ch else '',
                             ('TN' if ch.trunked else 'TF/unspecified') if ch else '',state,
                             ' '.join(inventory.label(n) for n in others),inventory.errors.get(address,''),
                             ch.raw.hex() if ch else '',inventory.port,inventory.baud,inventory.started,inventory.complete])
    inventory.path=str(path)
    return path


def read_all(port,name,baud,data_dir,log,cancel,progress,confirmed_last=False):
    result=Inventory(name,baud,confirmed_last)
    failures=0
    for index,address in enumerate([*range(1,1000),0],1):
        if cancel.is_set():
            result.cancelled=True
            break
        try:
            result.records[address]=read_address(port,address,log,name,baud)
            failures=0
        except (p.ProgrammingError,OSError) as exc:
            result.errors[address]=str(exc)
            failures+=1
        progress(index,result.records.get(address),address,result.errors.get(address,''))
        if failures>=3:
            break
    save_inventory(result,data_dir)
    return result
