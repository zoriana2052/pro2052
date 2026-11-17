"""Channel plans, CSV import/restore and snapshot comparison. No UI or serial access on import."""
import csv
import json
from pathlib import Path
from decimal import Decimal
import programming as p
import inventory as memory


def address(value):
    text=str(value).strip()
    if text in ('0','000','1000'): return 0
    return p.channel_number(text)


def label(n): return str(n or 1000)


def digits(value):
    if str(value).strip().replace(',','.') in ('0','0.0','0.00','0.000','0.0000'): return '00000000'
    return p.frequency_digits(value)


def next_empty(inv,start=1,reserved=()):
    for physical in range(start,1001):
        n=physical%1000
        if n not in reserved and n in inv.records and inv.records[n].digits=='00000000' and not inv.records[n].trunked:
            return n
    raise ValueError('Немає вільного каналу / No empty channel')


def load_file(path,inv=None,start=1,reserved=()):
    path=Path(path)
    if path.stat().st_size>5*1024*1024: raise ValueError('CSV/JSON > 5 MB')
    if path.suffix.lower()=='.json':
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        return {address(data['channel']):digits(data['old_frequency_mhz'])}
    with path.open(encoding='utf-8-sig',newline='') as file:
        sample=file.read(4096);file.seek(0)
        try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
        except csv.Error: dialect=csv.excel
        reader=csv.DictReader(file,dialect=dialect)
        if 'frequency_mhz' not in (reader.fieldnames or []):
            raise ValueError('Потрібна колонка frequency_mhz / frequency_mhz column required')
        result={}
        used=set(reserved)
        for line,row in enumerate(reader,2):
            if line>1001: raise ValueError('Максимум 1000 рядків / Maximum 1000 rows')
            if row.get('state')=='unread': continue  # Unknown is never interpreted as empty.
            try:
                if None in row: raise ValueError('Malformed CSV')
                value=digits(row['frequency_mhz'])
                if row.get('address','').strip(): n=address(row['address'])
                elif row.get('channel','').strip(): n=address(row['channel'])
                elif inv is not None: n=next_empty(inv,start,used)
                else: raise ValueError('channel column required')
                if n in result: raise ValueError('Repeated channel')
                result[n]=value;used.add(n)
            except (ValueError,p.ProgrammingError,KeyError) as exc:
                raise ValueError(f'CSV row {line}: {exc}') from exc
    return result


def validate_plan(inv,changes):
    if not inv.complete: raise ValueError('Спочатку прочитайте всі канали / Read all channels first')
    result={}
    for n,value in changes.items():
        if n not in inv.records: raise ValueError('Unknown channel')
        value=digits(p.mhz(value))
        old=inv.records[n]
        if old.digits==value: continue
        if old.trunked: raise ValueError(f'{label(n)}: trunking channel')
        # Reject transient duplicates too: swaps require a separately confirmed clear first.
        duplicates=inv.duplicates(value,n)
        if duplicates: raise ValueError(f'{label(n)}: duplicate {p.mhz(value)} MHz: '+', '.join(label(x) for x in duplicates))
        if value!='00000000' and value in result.values(): raise ValueError('Duplicate frequencies in proposed changes')
        result[n]=value
    return result


def compare(before,after):
    result=[]
    for n in sorted(before.keys()|after.keys(),key=lambda x:x or 1000):
        a,b=before.get(n),after.get(n)
        if a==b: continue
        kind='unknown' if a is None or b is None else 'added' if a=='00000000' else 'cleared' if b=='00000000' else 'changed'
        result.append((n,a,b,kind))
    return result


def apply_plan(port,inv,changes,data_dir,log,name,baud,cancel,progress):
    if (inv.port,inv.baud)!=(name,baud): raise ValueError('Inventory belongs to another connection')
    plan=validate_plan(inv,changes)
    # All targets must still match the reviewed snapshot BEFORE the first mutation.
    for n in plan:
        if cancel.is_set(): return []
        current=p.read_channel(port,n or 1000,log,name,baud)
        if current!=inv.records[n]: raise p.ProgrammingError('changed',label(n))
    memory.save_inventory(inv,data_dir)
    done=[]
    for n,value in plan.items():
        if cancel.is_set(): break
        actual,backup=p.program_channel(port,inv.records[n],p.mhz(value),data_dir,log,name,baud)
        done.append(n)
        progress(n,actual,str(backup))
    return done
