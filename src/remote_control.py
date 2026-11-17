"""Catalog of every PC command in PRO-2052 manual pp.47-51.
Syntax checks are not firmware validation. Underspecified trunking arguments remain explicit advanced input.
"""
from dataclasses import dataclass
import re
import radio
import programming as p

@dataclass(frozen=True)
class Action:
    id: str
    uk: str
    en: str
    prefix: str
    pattern: str = ''
    hint: str = ''
    category: str = 'status'
    mutation: bool = False
    memory: bool = False
    query: str = ''
    page: int = 48

ACTIONS=[]
def add(id,uk,en,prefix,pattern='',hint='',category='status',mutation=False,memory=False,query='',page=48):
    ACTIONS.append(Action(id,uk,en,prefix,pattern,hint,category,mutation,memory,query,page))

keys=[('SCAN','Сканування','Scan'),('MANUAL','Ручний режим','Manual'),('DIGIT','Цифра','Digit'),('CLEAR','Крапка / Clear','Decimal / Clear'),('ENTER','Введення E','Enter E'),('PRIORITY','Пріоритет / швидкість','Priority / speed'),('LOCKOUT','Блокування / Skip','Lockout / Skip'),('UP','Hold / вгору','Hold / up'),('DOWN','Limit / вниз','Limit / down'),('SEARCH','Пошук','Search'),('SERVICE','Сервісний пошук','Service search'),('DATA','Data / Alert','Data / Alert'),('DELAY','Затримка','Delay'),('TRUNK','Транкінг','Trunk'),('SHIFT','Shift','Shift')]
for i,(key,uk,en) in enumerate(keys):
    add('key_'+key,uk,en,f'KEY{i:02d}'+(' ' if i==2 else ''),r'[0-9]' if i==2 else '', '0–9' if i==2 else '', 'keys',True,i in (2,3,4,5,6,11,12,13,14),page=47)
for cmd,uk,en in [('MD','Режим','Mode'),('MA','Поточний канал','Current channel'),('SQ','Шумоподавлювач відкритий','Squelch open'),('DL','Затримка','Delay'),('DS','Пропуск даних','Data skip'),('LO','Блокування','Lockout'),('PR','Пріоритет','Priority'),('QU','Монітор шумоподавлювача','Squelch monitor'),('RI','Монітор пріоритету','Priority monitor'),('RM','Модуляція','Modulation'),('SB','Активні банки','Active banks'),('LL','Нижня межа пошуку','Lower search limit'),('LU','Верхня межа пошуку','Upper search limit'),('IC','Пам’ять Trunk ID','Trunk ID memory'),('ID','Монітор Trunk ID','Trunk ID monitor'),('AF','Формат EDACS ID','EDACS ID format'),('BT','S-Bit','S-Bit'),('FI','Ідентифікація частоти','Frequency identification'),('MU?','Приглушення: стан','Muting state'),('MU','Приглушення: режим','Muting mode'),('RG','Діапазон EDACS ID','EDACS ID range'),('SI','Інформація сканера','Scanner information'),('TB','Транкінгові банки','Trunking banks'),('TD','Виявлення тону','Tone detection')]:
    add('get_'+cmd,uk,en,cmd,page=51 if cmd in ('FI','MU?','MU','RG','SI','TB','TD') else 50 if cmd in ('IC','ID','AF','BT') else 49 if cmd in ('PR','QU','RI','RM','SB') else 48)
for prefix,uk,en in [('PR','Пріоритет','Priority'),('QU','Монітор шумоподавлювача','Squelch monitor'),('RI','Монітор пріоритету','Priority monitor'),('ID','Монітор Trunk ID','Trunk ID monitor'),('AF','AFS / десятковий EDACS ID','AFS / decimal EDACS ID'),('BT','S-Bit','S-Bit'),('FI','Ідентифікація частоти','Frequency identification'),('TD','Виявлення тону','Tone detection')]:
    for state in 'NF':add(prefix+state,uk+(' — увімкнути' if state=='N' else ' — вимкнути'),en+(' — on' if state=='N' else ' — off'),prefix+state,category='settings',mutation=True,memory=True,query=prefix,page=51 if prefix in ('FI','TD') else 50 if prefix in ('ID','AF','BT') else 49)
for state,uk,en in [('N','Увімкнути приглушення','Mute on'),('A','Автоматичне приглушення','Mute auto'),('F','Вимкнути приглушення','Mute off')]:add('MU'+state,uk,en,'MU'+state,category='settings',mutation=True,query='MU',page=51)
add('go_channel','Перейти до каналу','Go to channel','MA',r'\d{1,4}','1–1000','tuning',True,query='MA')
add('get_channel','Прочитати канал','Read channel','PM',r'\d{1,4}','1–1000')
for prefix,uk,en in [('RF','Налаштувати частоту без запису каналу','Tune frequency without channel write'),('LL','Задати нижню межу','Set lower limit'),('LU','Задати верхню межу','Set upper limit'),('SS','Додати частоту до пропуску пошуку','Add search-skip frequency')]:
    add('freq_'+prefix,uk,en,prefix,r'\d{1,4}(?:[.,]\d{1,4})?','MHz','tuning',True,prefix=='SS',prefix if prefix in ('LL','LU') else '',50 if prefix=='RF' else 49 if prefix=='SS' else 48)
add('get_skip','Прочитати комірку пропуску пошуку','Read search skip slot','SS',r'\d{2}','## — 2 digits; slot numbering not specified','banks',page=49)
add('get_priority','Пріоритетний канал банку','Bank priority channel','PC ',r'[A-T]','A–T = banks 1–20','banks',page=49)
add('set_priority','Задати пріоритетний канал банку','Set bank priority channel','PC ',r'[A-T][0-9]{3}','A001; 000 = channel 1000','banks',True,True,page=49)
add('set_banks','Вибрати банки сканування','Select scan banks','SB ',r'[A-T]{1,20}','A–T; CG = banks 3 and 7','banks',True,query='SB',page=49)
add('set_ic','Вибрати пам’ять Trunk ID','Set Trunk ID memory','IC ',r'[A-Z]','x: letter equivalent; manual does not specify mapping','trunk',True,True,'IC',50)
add('get_il','Перевірити блокування Trunk ID','Check Trunk ID lockout','IL',r'\d{3}','###','trunk',page=50)
add('il_type1','Блокувати Motorola Type I ID','Lock out Motorola Type I ID','ILR ',r'[0-7][0-9]{2}-[0-9]{2}','xyy-zz: block, fleet, subfleet','trunk',True,True,page=50)
add('il_type2','Блокувати Motorola Type II ID','Lock out Motorola Type II ID','ILR ',r'\d{6}','nnnnnn: six-digit ID','trunk',True,True,page=50)
add('il_edacs','Блокувати EDACS ID','Lock out EDACS ID','ILR ',r'\d{2}-\d{3}','xx-yyz: agency, fleet, subfleet','trunk',True,True,page=50)
add('fleet','Програмувати блок fleet map','Program fleet-map block','FB ',r'[A-T] [0-7] (?:0[0-9]|1[0-4])','bank block size; A 0 00','trunk',True,True,page=50)
add('get_pi','Прочитати пріоритет ID у списку','Read scan-list ID priority','PI ',r'\d{1,3}','# = ID location number (encoding not specified)','trunk',page=51)
add('set_pi','Задати пріоритет ID у списку','Set scan-list ID priority','PI ',r'\d{2,4}','@# = list + ID location; widths not specified','trunk',True,True,page=51)
add('set_rg','Задати діапазон EDACS ID','Set EDACS ID range','RG ',r'\d{2}-(?:\d{2})?','01- or 01-02','trunk',True,True,'RG',51)
# No invented mapping or defaults for these underspecified formats. The user supplies the manual-formatted parameters.
add('talkgroup','Програмувати Talk Group ID (розширене)','Program Talk Group ID (advanced)','TG ',r'[0-9]{1,2} [0-9]{3,5} [0-9]{2}-[0-9]{2}','* @%& ##-$$: bank; list/location/block; fleet/subfleet. Widths not specified.','trunk',True,True,page=51)
add('trunk_bank','Налаштувати транкінговий банк (розширене)','Set trunking bank (advanced)','TR ',r'[A-T] [0-9] [0-9]{8} [0-9]{4}','& # %%%%%%%% $$$$: bank, type code, base, offset. Type/offset encoding not specified.','trunk',True,True,'TB',51)
add('reset','ОЧИСТИТИ ВСЮ ПАМ’ЯТЬ','CLEAR ALL MEMORY','AC',category='maintenance',mutation=True,memory=True,page=48)
BY_ID={a.id:a for a in ACTIONS}
MODE_NAMES=['Scan','Manual','Limit Search','Limit Search Hold','Service Scan','Service Scan Hold','Program','EDACS Program','System Program','ID Search','ID Search Hold','ID Scan','ID Manual','ID Lockout Review','Search Control Channel','EDACS ID Search','EDACS ID Hold','EDACS ID Scan','EDACS ID Manual','EDACS ID Lockout Review','EDACS Search Control Channel','VFO']


def build(id,parameter=''):
    action=BY_ID[id];parameter=str(parameter).strip()
    if not re.fullmatch(action.pattern,parameter):raise ValueError('Параметри / Parameters: '+action.hint)
    if id in ('go_channel','get_channel'):parameter=f'{p.channel_number(parameter):03d}'
    if id.startswith('freq_'):parameter=p.frequency_digits(parameter)
    if id=='talkgroup' and not 1<=int(parameter.split()[0])<=20:raise ValueError('Bank: 1–20')
    if id=='trunk_bank':p.frequency_digits(p.mhz(parameter.split()[2]))
    if id=='set_banks' and len(set(parameter))!=len(parameter):raise ValueError('Duplicate bank letters')
    if id=='fleet':
        bank,block,size=parameter.split();block,size=int(block),int(size)
        if size==12 and block not in (0,2,4,6) or size==13 and block not in (0,4) or size==14 and block!=0:raise ValueError('Fleet block restriction, manual p.44')
    return action.prefix+parameter


def exchange(port,command,log,name,baud):
    # Only command strings rebuilt from the catalog reach here through execute().
    stale=radio.capture(port,.2)
    if stale:radio.record(log,event='unattributed_rx',raw_hex=stale.hex(),raw_ascii=repr(stale),source='remote')
    radio.record(log,event='remote_intent',port=name,baud=baud,query=command,source='remote')
    wire=command.encode('ascii')+b'\r'
    if port.write(wire)!=len(wire):raise OSError('Incomplete command write; result unknown')
    reply=radio.capture(port,1.5,stop_at_cr=True)
    radio.record(log,event='remote_reply',port=name,baud=baud,query=command,raw_hex=reply.hex(),raw_ascii=repr(reply),source='remote')
    return reply


def execute(port,id,parameter,log,name,baud,reset_confirmed=False):
    command=build(id,parameter);action=BY_ID[id]
    if id=='reset' and not reset_confirmed:raise ValueError('Reset requires explicit confirmation')
    reply=exchange(port,command,log,name,baud)
    rows=[(command,reply)]
    if not reply.endswith(b'\r') or reply.strip() in (b'NG',b'ERR',b'ORER') or reply.strip()==command.encode():
        return rows  # Unknown/rejected; do not retry or send follow-up mutation.
    if action.query:rows.append((action.query,exchange(port,action.query,log,name,baud)))
    return rows
