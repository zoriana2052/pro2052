"""Native limit search. Manual pp.47-50: LL/LU, KEY09 search, KEY01 manual.
Never infer a found frequency from a stored memory channel or from the configured bounds.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re
import uuid
import radio
import programming as p
from app_storage import atomic_json


def bounds(low,high):
    a,b=p.frequency_digits(low),p.frequency_digits(high)
    if int(a)>=int(b):raise ValueError('Lower frequency must be below upper frequency / Нижня межа має бути меншою')
    lower,upper=Decimal(p.mhz(a)),Decimal(p.mhz(b))
    if not any(Decimal(x)<=lower<upper<=Decimal(y) for x,y,_ in p.BANDS):
        raise ValueError('Use one supported band / Виберіть межі в одному діапазоні')
    return a,b


def exchange(port,command,log,name,baud):
    if command not in ('LL','LU','KEY09','KEY01') and not re.fullmatch(r'(LL|LU)[0-9]{8}',command):
        raise ValueError('Search command is not allowed')
    if len(command)==10:p.frequency_digits(p.mhz(command[2:]))
    stale=radio.capture(port,.2)
    if stale:radio.record(log,event='unattributed_rx',raw_hex=stale.hex(),raw_ascii=repr(stale),source='search')
    payload=command.encode('ascii')+b'\r'
    if port.write(payload)!=len(payload):raise OSError('Incomplete write')
    reply=radio.capture(port,1.5,stop_at_cr=True)
    radio.record(log,event='search_reply',port=name,baud=baud,query=command,raw_hex=reply.hex(),raw_ascii=repr(reply),source='search')
    return reply


def bound_value(raw,tag):
    match=re.fullmatch(rb'(?:'+tag.encode()+rb')?F?([0-9]{8})\r',raw)
    if not match:raise ValueError('Unrecognized search limit reply / Невідома відповідь межі: '+repr(raw))
    return match[1].decode()


def observed_frequency(raw):
    match=re.fullmatch(rb'(?:C[0-9]{3} )?F([0-9]{8})(?: TF(?: [A-Z0-9]+)*)?\r',raw)
    if not match:return None
    return match[1].decode()


def run_search(port,name,baud,low,high,data_dir,log,cancel,emit,known):
    low,high=bounds(low,high)
    folder=Path(data_dir)/'search-backups';folder.mkdir(parents=True,exist_ok=True)
    old={tag:exchange(port,tag,log,name,baud) for tag in ('LL','LU')}
    # Persist original bounds as both parsed frequencies and raw data before changing settings.
    parsed={tag:bound_value(raw,tag) for tag,raw in old.items()}
    atomic_json(folder/f'limits-{uuid.uuid4().hex}.json',dict(utc=datetime.now(timezone.utc).isoformat(),port=name,baud=baud,raw={k:v.hex() for k,v in old.items()},frequencies={k:p.mhz(v) for k,v in parsed.items()}))
    started=False
    try:
        for tag,value in [('LL',low),('LU',high)]:
            if cancel.is_set():return
            started=True
            reply=exchange(port,tag+value,log,name,baud)
            if reply!=b'OK\r' and bound_value(reply,tag)!=value:raise ValueError('Search limit rejected')
            if bound_value(exchange(port,tag,log,name,baud),tag)!=value:raise ValueError('Search limit verification failed')
        if cancel.is_set():return
        reply=exchange(port,'KEY09',log,name,baud)
        if reply.strip() in (b'NG',b'ERR',b'ORER') or not reply.endswith(b'\r'):raise ValueError('SEARCH rejected / SEARCH не підтверджено')
        misses=0
        while not cancel.is_set():
            mode=radio.exchange(port,'MD',log,name,baud)
            if mode not in (b'MD02\r',b'MD03\r'):raise ValueError('Scanner is not in limit search / Сканер не в режимі пошуку: '+repr(mode))
            first=radio.exchange(port,'MA',log,name,baud)
            sq=radio.exchange(port,'SQ',log,name,baud)
            if sq not in (b'+\r',b'-\r'):raise ValueError('SQ response not confirmed / SQ не підтверджено')
            value=observed_frequency(first)
            if sq==b'+\r' and value and int(low)<=int(value)<=int(high):
                second=radio.exchange(port,'MA',log,name,baud)
                mode2=radio.exchange(port,'MD',log,name,baud)
                if observed_frequency(second)==value and mode2 in (b'MD02\r',b'MD03\r'):
                    stamp=datetime.now().astimezone().isoformat(timespec='seconds')
                    membership='unknown' if known is None else 'known' if value in known else 'new'
                    radio.record(log,event='search_observation',port=name,baud=baud,frequency_mhz=p.mhz(value),source='SEARCH-MA-SQ-MA',note=membership)
                    emit('hit',(value,stamp,membership));misses=0
            if value is None:
                misses+=1
                if misses==5:emit('notice','No confirmed MA frequency / MA не повідомляє підтверджену частоту. Дивіться сирий журнал.')
            cancel.wait(.25)
    finally:
        if started:
            exchange(port,'KEY01',log,name,baud)
            if radio.exchange(port,'MD',log,name,baud)!=b'MD01\r':
                raise ValueError('Could not confirm MANUAL on exit. Stop search on scanner / Вихід у MANUAL не підтверджено; зупиніть пошук на сканері.')
