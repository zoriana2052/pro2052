from platform_support import normalize_port, valid_port, open_folder
import csv
import os
import traceback
import logging
from datetime import datetime
from pathlib import Path
import queue
import re
import threading
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import radio
from ui_language import LanguageUI
from periods import Periods
from app_storage import VERSION, app_folder, data_folder, prepare_data, load_connection, atomic_json
from history import HistoryWindow
from frequency_names import FrequencyNames, ask_name, frequency_key

BASE = Path(__file__).resolve().parent
POLL_DELAYS = {'Звичайне': 1.0, 'Швидше': 0.25, 'Normal': 1.0, 'Faster': 0.25}

def monitor(name, baud, path, stop, events, cycle_delay=1.0):
    try:
        import serial
        with serial.Serial(port=None, baudrate=baud, bytesize=8, parity='N', stopbits=1,
                           timeout=0.1, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False) as port:
            port.dtr = False
            port.rts = False
            port.port = name
            port.open()
            radio.record(path, event='session_start', port=name, baud=baud, source='desktop', note=f'Pause between cycles: {cycle_delay} s')
            with path.open(encoding='utf-8', newline='') as source:
                reader = csv.DictReader(source)
                while not stop.is_set():
                    ok = radio.poll_once(port, ['MD', 'MA', 'SQ'], path, name, baud, activity=True)
                    for row in reader:
                        events.put(('row', row))
                    if not ok:
                        events.put(('error', 'Опитування зупинено. Перевірте діагностику, REMOTE та швидкість.'))
                        break
                    stop.wait(cycle_delay)
    except Exception as exc:
        logging.exception('Serial monitoring failed')
        events.put(('error', f'{type(exc).__name__}: {exc}'))
    finally:
        events.put(('done', None))

class App:
    def __init__(self, root, data_dir=None):
        self.root, self.events, self.stop_event = root, queue.Queue(), threading.Event()
        self.worker, self.closing, self.failed, self.count = None, False, False, 0
        self.data_dir = prepare_data(data_dir or data_folder())
        from appearance import apply_theme
        apply_theme(root)
        self.connection = load_connection(self.data_dir / 'connection.json')
        self.names = FrequencyNames(self.data_dir / 'frequency-names.json')
        self.periods = Periods()
        self.period_item = None
        root.title('PRO-2052 — Журнал активності')
        root.geometry(f'{min(1040, root.winfo_screenwidth()-40)}x{min(760, root.winfo_screenheight()-100)}')
        root.minsize(850, 580)
        root.protocol('WM_DELETE_WINDOW', self.close)
        main = ttk.Frame(root, padding=12)
        main.pack(fill='both', expand=True)
        from appearance import make_header
        make_header(main, VERSION)
        ttk.Label(main, text='Частоти й час спостережень', font=('Helvetica Neue', 11)).pack(anchor='w', pady=(2,8))
        banner = ttk.Frame(main, padding=(0, 2, 0, 4))
        banner.pack(fill='x', pady=(0, 8))
        flag = tk.Canvas(banner, width=36, height=24, highlightthickness=0,
                         borderwidth=0)
        flag.create_rectangle(0, 0, 36, 12, fill='#0057B7', outline='')
        flag.create_rectangle(0, 12, 36, 24, fill='#FFD700', outline='')
        flag.pack(side='left', padx=(0, 10))
        credit = ttk.Label(banner,
                           text='Proudly made in Ukraine by pro2052',
                           font=('Helvetica Neue', 10), foreground='#334155',
                           anchor='w', justify='left')
        credit.pack(side='left', fill='x', expand=True)
        banner.bind('<Configure>', lambda event: credit.configure(
            wraplength=max(200, event.width - 50)))
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True)
        monitor_tab = ttk.Frame(self.notebook)
        program_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(monitor_tab, text='Моніторинг')
        self.notebook.add(program_tab, text='Програмування каналів')
        main = monitor_tab
        bar = ttk.Frame(main)
        bar.pack(fill='x')
        ttk.Label(bar, text='Порт').pack(side='left')
        self.port, self.baud = tk.StringVar(value=self.connection['port']), tk.StringVar(value=self.connection['baud'])
        self.ports = ttk.Combobox(bar, textvariable=self.port, width=10)
        self.ports.pack(side='left', padx=6)
        self.refresh_button = ttk.Button(bar, text='Оновити порти', command=self.refresh)
        self.refresh_button.pack(side='left', padx=6)
        ttk.Label(bar, text='Швидкість').pack(side='left', padx=(12,0))
        self.bauds = ttk.Combobox(bar, textvariable=self.baud, values=['2400','4800','9600','19200'], state='readonly', width=8)
        self.bauds.pack(side='left', padx=6)
        self.start_button = ttk.Button(bar, text='Почати', command=self.start, style='Accent.TButton')
        self.start_button.pack(side='left', padx=6)
        self.stop_button = ttk.Button(bar, text='Зупинити', command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        pace_bar = ttk.Frame(main)
        pace_bar.pack(fill='x', pady=(10, 0))
        ttk.Label(pace_bar, text='Опитування').pack(side='left')
        self.pace = tk.StringVar(value='Швидше' if self.connection['pace']=='fast' else 'Звичайне')
        self.paces = ttk.Combobox(pace_bar, textvariable=self.pace,
                                 values=['Звичайне', 'Швидше'], state='readonly', width=12)
        self.paces.pack(side='left', padx=6)
        ttk.Label(pace_bar, text='Змінюйте режим після зупинки запису.').pack(side='left', padx=8)
        self.status = tk.StringVar(value='Готово. Увімкніть REMOTE: SFT має блимати.')
        ttk.Label(main, textvariable=self.status, wraplength=800).pack(anchor='w', pady=(16,8))
        self.summary = tk.StringVar(value='Спостережень: 0')
        summary_bar = ttk.Frame(main)
        summary_bar.pack(fill='x', pady=8)
        ttk.Label(summary_bar, textvariable=self.summary, font=('Helvetica Neue',11,'bold')).pack(side='left')
        ttk.Button(summary_bar, text='Відкрити журнал', command=lambda: HistoryWindow(self)).pack(side='right', padx=8)
        frame = ttk.Frame(main)
        frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('first','last','channel','samples','name','frequency'), show='headings', height=5)
        for key,title,width in [('first','Перше виявлення',270),('last','Останнє виявлення',270),('channel','Канал',65),('samples','Спостережень',110),('name','Назва',180),('frequency','Частота, МГц',120)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=width, anchor='w')
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        horizontal = ttk.Scrollbar(main, orient='horizontal', command=self.tree.xview)
        self.tree.configure(xscrollcommand=horizontal.set)
        horizontal.pack(fill='x')
        self.tree.bind('<Double-1>', self.edit_frequency_name)
        self.tree.bind('<Return>', self.edit_frequency_name)
        ttk.Label(main, text='Двічі натисніть рядок, щоб назвати частоту.').pack(anchor='w', pady=(6,0))
        ttk.Label(main, text='Рядок — період спостережень, не гарантовано безперервна розмова. Час ПК із часовим зсувом.', wraplength=800).pack(anchor='w', pady=8)
        ttk.Label(main, text='Діагностика — останні відповіді сканера').pack(anchor='w')
        self.detail = tk.Text(main, height=3, wrap='word', state='disabled', font=('Menlo',10), background='#fffafd', foreground='#49364f', relief='flat', highlightthickness=1, highlightbackground='#e3d6e8')
        self.detail.pack(fill='x', pady=4)
        self.log_path = tk.StringVar(value='Журнали зберігаються у вашій папці даних → logs.')
        ttk.Entry(main, textvariable=self.log_path, state='readonly').pack(fill='x', pady=6)
        footer = ttk.Frame(main)
        footer.pack(fill='x', pady=(4,0))
        ttk.Label(main, text='Після завершення вимкніть REMOTE, щоб користуватися кнопками сканера.').pack(anchor='w', pady=4)
        ttk.Button(footer, text='Папка даних', command=self.open_data_folder).pack(side='left')
        ttk.Button(footer, text='Імпортувати дані…', command=self.import_data).pack(side='left', padx=8)
        self.reconnect_button = ttk.Button(footer, text='Підключитися знову', command=self.start, state='disabled')
        self.reconnect_button.pack(side='left', padx=8)
        self.language_ui = LanguageUI(self, pace_bar, self.data_dir / 'ui-settings.json')
        from programming_ui import ProgrammingPanel
        self.programming = ProgrammingPanel(self, program_tab)
        from search_ui import SearchPanel
        self.search = SearchPanel(self)
        from remote_ui import RemotePanel
        self.remote = RemotePanel(self)
        self.language_ui.apply()
        self.refresh()
        root.after(100, self.drain)

    def save_connection(self):
        try:
            atomic_json(self.data_dir / 'connection.json', {
                'port': normalize_port(self.port.get()), 'baud': self.baud.get(),
                'pace': 'fast' if self.pace.get() in ('Швидше','Faster') else 'normal'})
            return True
        except OSError as exc:
            messagebox.showerror(self.language_ui.text('Налаштування'),
                                 self.language_ui.text('Не вдалося зберегти налаштування.')+'\n'+str(exc), parent=self.root)
            return False

    def import_data(self):
        t = self.language_ui.text
        if self.worker is not None or self.programming.busy:
            messagebox.showinfo(t('Імпорт даних'), t('Спочатку зупиніть роботу зі сканером.'), parent=self.root)
            return
        source = filedialog.askdirectory(title=t('Виберіть папку старої програми або її папку data'), parent=self.root)
        if not source:
            return
        try:
            from app_storage import import_legacy_data
            count = import_legacy_data(source, self.data_dir)
            self.names = FrequencyNames(self.data_dir / 'frequency-names.json')
            messagebox.showinfo(t('Імпорт даних'), t('Скопійовано файлів: ') + str(count) + '\n' + t('Наявні файли не замінено. Перезапустіть програму, щоб застосувати налаштування.'), parent=self.root)
        except (OSError, ValueError) as exc:
            messagebox.showerror(t('Імпорт даних'), str(exc), parent=self.root)

    def open_data_folder(self):
        try:
            open_folder(self.data_dir)
        except OSError as exc:
            messagebox.showerror(self.language_ui.text('Папка даних'), str(exc), parent=self.root)

    def edit_frequency_name(self, event=None):
        if event is not None and getattr(event, 'keysym', '') != 'Return':
            item = self.tree.identify_row(event.y)
        else:
            selected = self.tree.selection()
            item = selected[0] if selected else ''
        if not item:
            return
        # Capture frequency before opening the dialog: incoming rows can reorder the table.
        frequency = self.tree.set(item, 'frequency')
        t = self.language_ui.text
        if self.names.load_error:
            messagebox.showerror(t('Назва частоти'), t('Не вдалося прочитати файл назв. Початковий файл збережено.') + '\n' + self.names.load_error, parent=self.root)
            return
        name = ask_name(self.root, frequency, self.names.get(frequency), t)
        if name is None:
            return
        try:
            self.names.save(frequency, name)
        except (OSError, ValueError) as exc:
            messagebox.showerror(t('Назва частоти'), t('Не вдалося зберегти назву.') + '\n' + str(exc), parent=self.root)
            return
        for row in self.tree.get_children():
            if frequency_key(self.tree.set(row, 'frequency')) == frequency_key(frequency):
                self.tree.set(row, 'name', self.names.get(frequency))

    def refresh(self):
        try:
            from serial.tools import list_ports
            names = [p.device for p in list_ports.comports()]
            self.ports['values'] = names
            if names and self.port.get() not in names:
                self.status.set('Збережений порт недоступний. Виберіть порт адаптера.')
        except ImportError:
            self.status.set('Потрібен pyserial: встановіть залежності з requirements.txt.')
        except Exception as exc:
            self.status.set(f'Не вдалося прочитати порти: {exc}')

    def start(self):
        if self.programming.busy or self.worker is not None:
            return
        name = normalize_port(self.port.get())
        if not valid_port(name):
            messagebox.showerror(self.language_ui.text('Порт'), self.language_ui.text('Виберіть порт сканера зі списку.'))
            return
        path = self.data_dir / 'logs' / f'activity-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.csv'
        if not self.save_connection():
            return
        self.reconnect_button['state'] = 'disabled'
        self.log_path.set(str(path))
        self.count, self.failed = 0, False
        self.periods = Periods()
        self.period_item = None
        self.summary.set('Спостережень: 0')
        self.tree.delete(*self.tree.get_children())
        self.stop_event.clear()
        for widget in (self.start_button,self.refresh_button,self.ports,self.bauds,self.paces):
            widget['state'] = 'disabled'
        self.stop_button['state'] = 'normal'
        self.status.set('Підключення та перевірка відповіді…')
        self.worker = threading.Thread(target=monitor, args=(name,int(self.baud.get()),path,self.stop_event,self.events,POLL_DELAYS[self.pace.get()]), daemon=False)
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        self.stop_button['state'] = 'disabled'
        self.status.set('Завершуємо поточну перевірку й закриваємо порт…')

    def close(self):
        self.save_connection()
        self.closing = True
        if self.programming.busy:
            self.programming.cancel_scan.set()
            self.root.after(100, self.close)
            return
        if self.worker:
            self.stop()
        else:
            self.root.destroy()

    def diagnostic(self, text):
        self.detail.configure(state='normal')
        self.detail.insert('end', self.language_ui.text(text) + '\n')
        if int(self.detail.index('end-1c').split('.')[0]) > 100:
            self.detail.delete('1.0', '2.0')
        self.detail.see('end')
        self.detail.configure(state='disabled')

    def drain(self):
        for _ in range(300):
            try:
                kind,data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'error':
                self.failed = True
                self.periods.close()
                self.status.set('Зв’язок перервано або сканер не відповів. Перевірте кабель і REMOTE, потім підключіться знову.')
                self.diagnostic(data)
            elif kind == 'row':
                grouped = self.periods.feed(data)
                if data['event'] == 'activity_observation' and grouped:
                    period, new = grouped
                    self.count += 1
                    values = (period.first, period.last, period.channel, period.count, self.names.get(period.frequency), period.frequency)
                    if new or not self.period_item or not self.tree.exists(self.period_item):
                        self.period_item = self.tree.insert('', 0, values=values)
                    else:
                        self.tree.item(self.period_item, values=values)
                    children = self.tree.get_children()
                    if len(children) > 1000:
                        self.tree.delete(children[-1])
                    self.summary.set(f'Спостережень: {self.count} • У таблиці останні 1000 періодів, у CSV — усі спостереження')
                elif data['query']:
                    self.diagnostic(f"{data['local'][11:19]}  {data['query']}: {data['raw_ascii']}")
                    if not self.stop_event.is_set() and data['query']=='SQ':
                        self.status.set({'2b0d':'Шумоподавлювач відкритий. Спостерігаємо…','2d0d':'Шумоподавлювач закритий. Спостерігаємо…'}.get(data['raw_hex'],'Отримано SQ. Дивіться діагностику.'))
            elif kind == 'done':
                self.periods.close()
                self.root.after(50,self.finished)
        self.root.after(100,self.drain)

    def finished(self):
        if self.worker and self.worker.is_alive():
            self.root.after(50,self.finished)
            return
        self.worker = None
        if self.closing:
            self.root.destroy()
            return
        if not self.failed:
            self.status.set('Зупинено. Порт закрито; записані дані збережено.')
        self.start_button['state'] = self.refresh_button['state'] = 'normal'
        self.ports['state'],self.bauds['state'] = 'normal','readonly'
        self.paces['state'] = 'readonly'
        self.stop_button['state'] = 'disabled'
        self.reconnect_button['state'] = 'normal' if self.failed else 'disabled'

if __name__ == '__main__':
    from launcher import main
    main()
