"""Read-only CSV history viewer. Uses only explicitly logged activity records."""
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from periods import Periods
from frequency_names import frequency_key

REQUIRED = {'event','local','utc','query','raw_hex','frequency_mhz','note'}

def load_history(path, cancel=None, daily=None):
    path = Path(path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('CSV exceeds 50 MB')
    groups, skipped, rows = [], 0, 0
    grouper = Periods()
    daily_totals = {}
    with path.open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError('Not a PRO-2052 observation log: required columns are missing')
        for row in reader:
            if cancel and cancel.is_set():
                return None
            rows += 1
            try:
                if None in row or any(row.get(k) is None for k in REQUIRED):
                    raise ValueError('Incomplete row')
                if row['event'] == 'activity_observation':
                    frequency_key(row['frequency_mhz'])
                    stamp = datetime.fromisoformat(row['local'])
                    if stamp.tzinfo is None:
                        raise ValueError('Missing timezone')
                result = grouper.feed(row)
                if row['event'] == 'activity_observation' and result is None:
                    raise ValueError('Invalid observation')
                if result and result[1]:
                    groups.append(result[0])
                if result and daily is not None:
                    key = (stamp.date().isoformat(), frequency_key(row['frequency_mhz']))
                    if key not in daily_totals:
                        daily_totals[key] = dict(day=key[0], frequency=result[0].frequency,
                                                first=row['local'], last=row['local'],
                                                first_stamp=stamp, last_stamp=stamp, samples=0, periods=set())
                    total = daily_totals[key]
                    total['samples'] += 1
                    total['periods'].add(len(groups))
                    if stamp < total['first_stamp']:
                        total['first'], total['first_stamp'] = row['local'], stamp
                    if stamp > total['last_stamp']:
                        total['last'], total['last_stamp'] = row['local'], stamp
            except (ValueError, TypeError, InvalidOperation):
                skipped += 1
                grouper.close()
    if daily is not None:
        daily.extend(dict(day=v['day'], frequency=v['frequency'], first=v['first'],
                          last=v['last'], samples=v['samples'], periods=len(v['periods']))
                     for v in daily_totals.values())
    return groups, skipped, rows


def filter_periods(groups, names, frequency='', name='', day=''):
    day = day.strip()
    target = date.fromisoformat(day) if day else None
    frequency = frequency.strip().replace(',', '.')
    name = name.strip().casefold()
    return [p for p in groups
            if frequency in p.frequency
            and name in names.get(p.frequency).casefold()
            and (target is None or date.fromisoformat(p.first[:10]) <= target <= date.fromisoformat(p.last[:10]))]


def filter_daily(totals, names, frequency='', name='', day='', by_periods=False):
    day = day.strip()
    if day:
        day = date.fromisoformat(day).isoformat()
    frequency = frequency.strip().replace(',', '.')
    name = name.strip().casefold()
    matches = [v for v in totals if (not day or v['day'] == day)
               and frequency in v['frequency']
               and name in names.get(v['frequency']).casefold()]
    return sorted(matches, key=lambda v: (-v['periods'], v['day'], Decimal(v['frequency']))
                  if by_periods else (Decimal(v['frequency']), v['day']))


class HistoryWindow:
    def __init__(self, app):
        self.app, self.t = app, app.language_ui.text
        # Freeze language for this independent window; reopening uses the new language.
        from ui_language import translate
        lang = app.language_ui.language
        self.t = lambda value: translate(value, lang)
        self.top = tk.Toplevel(app.root)
        self.top.title(self.t('Історія активності'))
        self.top.geometry('1080x620')
        self.top.minsize(850,500)
        self.closed, self.loading = False, False
        self.groups, self.matches, self.page = [], [], 0
        self.daily = []
        self.summary_mode = False
        self.results, self.cancel = queue.Queue(), threading.Event()
        self.top.protocol('WM_DELETE_WINDOW',self.close)
        main = ttk.Frame(self.top,padding=14)
        main.pack(fill='both',expand=True)
        bar = ttk.Frame(main)
        bar.pack(fill='x')
        self.open_button = ttk.Button(bar,text=self.t('Відкрити журнал'),command=self.choose)
        self.open_button.pack(side='left')
        self.path = tk.StringVar()
        ttk.Entry(bar,textvariable=self.path,state='readonly').pack(side='left',fill='x',expand=True,padx=10)
        filters = ttk.Frame(main)
        filters.pack(fill='x',pady=12)
        self.frequency,self.name,self.day = tk.StringVar(),tk.StringVar(),tk.StringVar()
        for label,var,width in [('Частота, МГц',self.frequency,13),('Назва',self.name,20),('Дата РРРР-ММ-ДД',self.day,13)]:
            ttk.Label(filters,text=self.t(label)).pack(side='left',padx=(0,5))
            entry=ttk.Entry(filters,textvariable=var,width=width)
            entry.pack(side='left',padx=(0,10))
            entry.bind('<Return>',lambda event:self.apply())
        ttk.Button(filters,text=self.t('Застосувати'),command=self.apply).pack(side='left')
        ttk.Button(filters,text=self.t('Скинути'),command=self.reset).pack(side='left',padx=5)
        views = ttk.Frame(main)
        views.pack(fill='x', pady=(0,10))
        ttk.Label(views,text=self.t('Показувати')).pack(side='left')
        self.view = ttk.Combobox(views, values=[self.t('Періоди активності'),self.t('Підсумок за день')],state='readonly',width=24)
        self.view.current(0)
        self.view.pack(side='left',padx=6)
        self.view.bind('<<ComboboxSelected>>',lambda event:self.apply())
        ttk.Label(views,text=self.t('Сортування підсумку')).pack(side='left',padx=(12,0))
        self.sort = ttk.Combobox(views,values=[self.t('За частотою'),self.t('За кількістю періодів')],state='readonly',width=24)
        self.sort.current(0)
        self.sort.pack(side='left',padx=6)
        self.sort.bind('<<ComboboxSelected>>',lambda event:self.apply())
        self.status=tk.StringVar(value=self.t('Виберіть CSV-журнал. Сканер не потрібен.'))
        ttk.Label(main,textvariable=self.status,wraplength=1000).pack(anchor='w',pady=(0,8))
        table=ttk.Frame(main)
        table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('first','last','channel','samples','name','frequency'),show='headings')
        for key,label,width in [('first','Перше виявлення',260),('last','Останнє виявлення',260),('channel','Канал',65),('samples','Спостережень',100),('name','Назва',180),('frequency','Частота, МГц',120)]:
            self.tree.heading(key,text=self.t(label))
            self.tree.column(key,width=width,minwidth=width)
        vertical=ttk.Scrollbar(table,command=self.tree.yview)
        self.tree.configure(yscrollcommand=vertical.set)
        self.tree.pack(side='left',fill='both',expand=True)
        vertical.pack(side='right',fill='y')
        horizontal=ttk.Scrollbar(main,orient='horizontal',command=self.tree.xview)
        horizontal.pack(fill='x')
        self.tree.configure(xscrollcommand=horizontal.set)
        nav=ttk.Frame(main)
        nav.pack(fill='x',pady=8)
        self.previous=ttk.Button(nav,text=self.t('Попередня'),command=lambda:self.turn(-1))
        self.previous.pack(side='left')
        self.next=ttk.Button(nav,text=self.t('Наступна'),command=lambda:self.turn(1))
        self.next.pack(side='left',padx=6)
        ttk.Button(nav,text=self.t('Експорт результатів CSV'),command=self.export).pack(side='right')
        self.page_text=tk.StringVar()
        ttk.Label(nav,textvariable=self.page_text).pack(side='left',padx=10)
        ttk.Label(main,text=self.t('Дата — місцева дата з журналу. Назви — поточні збережені підписи. CSV не змінюється.'),wraplength=1000).pack(anchor='w')
        self.hint = ttk.Label(main,text=self.t('Періоди — спостереження, не кількість розмов. Один період через північ може враховуватися в обох днях.'),wraplength=1000)
        self.hint.pack(anchor='w',pady=(6,0))
        self.render()
        self.top.after(100,self.drain)

    def choose(self):
        if self.loading: return
        path=filedialog.askopenfilename(parent=self.top,title=self.t('Відкрити журнал'),initialdir=str(self.app.data_dir/'logs'),filetypes=[('CSV','*.csv')])
        if not path: return
        self.loading=True
        self.open_button['state']='disabled'
        self.status.set(self.t('Читаємо журнал…'))
        def read():
            try:
                daily = []
                loaded = load_history(path,self.cancel,daily)
                self.results.put(('loaded',path,(loaded,daily) if loaded is not None else None))
            except Exception as exc: self.results.put(('error',path,str(exc)))
        threading.Thread(target=read,daemon=True).start()

    def drain(self):
        if self.closed: return
        try:
            kind,path,data=self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.loading=False
            self.open_button['state']='normal'
            if kind=='error':
                self.status.set(self.t('Не вдалося прочитати журнал.'))
                messagebox.showerror(self.t('Історія активності'),str(data),parent=self.top)
            elif data is not None:
                loaded,self.daily=data
                self.groups,skipped,rows=loaded
                self.path.set(path)
                self.reset()
                self.status.set(self.t('Рядків: {rows}. Періодів: {periods}. Пропущено пошкоджених рядків: {skipped}.').format(rows=rows,periods=len(self.groups),skipped=skipped))
                if not self.groups:
                    self.status.set(self.status.get()+' '+self.t('Немає підтверджених записів активності; сирі відповіді не перетворюємо на передачі.'))
        self.top.after(100,self.drain)

    def apply(self):
        try:
            summary_mode = self.view.current() == 1
            if summary_mode:
                matches=filter_daily(self.daily,self.app.names,self.frequency.get(),self.name.get(),self.day.get(), self.sort.current()==1)
            else:
                matches=filter_periods(self.groups,self.app.names,self.frequency.get(),self.name.get(),self.day.get())
        except ValueError:
            messagebox.showerror(self.t('Дата'),self.t('Введіть дату РРРР-ММ-ДД або залиште поле порожнім.'),parent=self.top)
            return
        self.summary_mode = summary_mode
        self.matches=matches if summary_mode else list(reversed(matches))
        self.page=0
        self.render()

    def reset(self):
        for var in (self.frequency,self.name,self.day): var.set('')
        self.apply()

    def turn(self,delta):
        self.page=max(0,min(self.page+delta,max(0,(len(self.matches)-1)//1000)))
        self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children())
        columns = ([('day','Дата',110),('frequency','Частота, МГц',120),('name','Назва',180),
                    ('first','Перше виявлення',260),('last','Останнє виявлення',260),
                    ('samples','Спостережень',100),('periods','Періодів',90)] if self.summary_mode else
                   [('first','Перше виявлення',260),('last','Останнє виявлення',260),('channel','Канал',65),
                    ('samples','Спостережень',100),('name','Назва',180),('frequency','Частота, МГц',120)])
        self.tree['columns'] = tuple(key for key,label,width in columns)
        for key,label,width in columns:
            self.tree.heading(key,text=self.t(label))
            self.tree.column(key,width=width,minwidth=width)
        for p in self.matches[self.page*1000:(self.page+1)*1000]:
            values = ((p['day'],p['frequency'],self.app.names.get(p['frequency']),p['first'],p['last'],p['samples'],p['periods'])
                      if self.summary_mode else (p.first,p.last,p.channel,p.count,self.app.names.get(p.frequency),p.frequency))
            self.tree.insert('','end',values=values)
        pages=max(1,(len(self.matches)+999)//1000)
        self.page_text.set(self.t('Рядків підсумку: {count}. Сторінка {page}/{pages}.' if self.summary_mode else 'Знайдено періодів: {count}. Сторінка {page}/{pages}.').format(count=len(self.matches),page=self.page+1,pages=pages))
        self.previous['state']='normal' if self.page else 'disabled'
        self.next['state']='normal' if self.page+1<pages else 'disabled'

    def export(self):
        if self.loading: return
        path=filedialog.asksaveasfilename(parent=self.top,title=self.t('Експорт результатів CSV'),defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        try:
            fields=['day','frequency_mhz','name','first','last','samples','periods'] if self.summary_mode else ['first','last','channel','samples','name','frequency_mhz']
            with open(path,'w',encoding='utf-8-sig',newline='') as file:
                writer=csv.writer(file);writer.writerow(fields)
                for row in self.matches:
                    frequency=row['frequency'] if self.summary_mode else row.frequency
                    name=self.app.names.get(frequency)
                    if name.startswith(('=','+','-','@')):name="'"+name
                    values=[row['day'],frequency,name,row['first'],row['last'],row['samples'],row['periods']] if self.summary_mode else [row.first,row.last,row.channel,row.count,name,frequency]
                    writer.writerow(values)
        except OSError as exc:messagebox.showerror(self.t('Експорт результатів CSV'),str(exc),parent=self.top)

    def close(self):
        self.closed=True
        self.cancel.set()
        self.top.destroy()
