from platform_support import normalize_port, valid_port, open_folder
"""Asynchronous single-channel editor. The UI never performs serial I/O."""
from datetime import datetime
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import uuid
import programming as protocol
import inventory as memory

STRINGS = {
 'tools': ('Редактор / CSV / відновлення', 'Editor / CSV / restore'),
 'batch_done': ('Завершено запис каналів: {count}. Для керування кнопками вимкніть REMOTE.', 'Channels written: {count}. Turn REMOTE off to use scanner buttons.'),
 'read_all': ('Прочитати всі канали', 'Read all channels'),
 'cancel_read': ('Скасувати читання', 'Cancel reading'),
 'verify_last': ('Перевірити канал 1000', 'Verify channel 1000'),
 'mapping_prompt': ('На самому сканері натисніть MANUAL, введіть 1000 та ще раз MANUAL. Переконайтеся, що на екрані канал 1000.\n\nНатисніть «Так», щоб прочитати та зіставити його з адресою 000. Частоти не змінюються.', 'On the scanner, press MANUAL, enter 1000, then press MANUAL again. Confirm that the display shows channel 1000.\n\nClick Yes to read and compare it with address 000. Frequencies will not be changed.'),
 'mapping': ('Адресу каналу 1000 не підтверджено. Виберіть його вручну на сканері в режимі MANUAL і повторіть перевірку.', 'Channel 1000 address is not confirmed. Select it manually on the scanner in MANUAL mode and verify again.'),
 'mapped': ('Адресу каналу 1000 перевірено. Тепер прочитайте всі канали.', 'Channel 1000 address verified. Now read all channels.'),
 'scan_progress': ('Прочитано адрес: {count}/1000. Це може тривати кілька хвилин.', 'Addresses processed: {count}/1000. This may take a few minutes.'),
 'scan_complete': ('Усі 1000 каналів прочитано. Копія: {path}', 'All 1000 channels read. Snapshot: {path}'),
 'scan_partial': ('Список неповний: підтверджено адрес {count}/1000. Повторіть читання. Запис заблоковано. Копія: {path}', 'Incomplete inventory: {count}/1000 addresses read. Repeat reading. Writing is blocked. Snapshot: {path}'),
 'inventory_required': ('Спочатку прочитайте всі канали для цього порту. Це потрібно для перевірки дублікатів.', 'Read all channels for this port first. This is required for duplicate checking.'),
 'duplicate': ('Ця частота вже є в інших каналах. Запис дубліката заблоковано. Канали:', 'This frequency already exists in other channels. Duplicate write blocked. Channels:'),
 'only_duplicates': ('Лише дублікати', 'Duplicates only'),
 'empty': ('Порожній', 'Empty'),
 'stored': ('Записаний', 'Stored'),
 'unread': ('Не прочитано', 'Unread'),
 'table_channel': ('Канал', 'Channel'),
 'table_frequency': ('Частота, МГц', 'Frequency, MHz'),
 'table_state': ('Стан', 'State'),
 'table_duplicates': ('Та сама частота в каналах', 'Same frequency in channels'),
 'inventory_note': ('Список — знімок пам’яті на час читання. Після ручних змін на сканері прочитайте його знову. Двічі натисніть канал для редагування.', 'This list is a snapshot. Read it again after manual scanner changes. Double-click a channel to edit.'),
 'title': ('Програмування каналів', 'Channel programming'),
 'intro': ('Зупиніть моніторинг. Виберіть канал, прочитайте його та введіть нову частоту.', 'Stop monitoring. Select and read a channel, then enter its new frequency.'),
 'channel_label': ('Канал (1–1000)', 'Channel (1–1000)'),
 'read': ('Прочитати канал', 'Read channel'),
 'frequency_label': ('Нова частота, МГц', 'New frequency, MHz'),
 'write': ('Переглянути й записати…', 'Review and write…'),
 'ready': ('Готово до читання каналу.', 'Ready to read a channel.'),
 'current': ('Зараз у каналі {channel}: {frequency} МГц', 'Current channel {channel}: {frequency} MHz'),
 'reading': ('Читаємо канал…', 'Reading channel…'),
 'writing': ('Зберігаємо копію, записуємо й перевіряємо…', 'Backing up, writing and verifying…'),
 'verified': ('Запис перевірено: канал {channel}, {frequency} МГц.\nКопія: {backup}', 'Write verified: channel {channel}, {frequency} MHz.\nBackup: {backup}'),
 'confirm': ('Канал {channel} · {port} · {baud}\n\nБуло: {old} МГц\nБуде: {new} МГц\n\nЗамінити частоту цього каналу? Перед записом буде збережено його поточне значення.', 'Channel {channel} · {port} · {baud}\n\nOld: {old} MHz\nNew: {new} MHz\n\nReplace this channel frequency? Its current value will be backed up before writing.'),
 'limits': ('Копії: data/channel-backups та data/channel-inventories. Після операції вимкніть REMOTE для керування кнопками.', 'Backups: data/channel-backups and data/channel-inventories. Turn REMOTE off after operations to use scanner buttons.'),
 'stop': ('Спочатку зупиніть моніторинг і дочекайтеся закриття порту.', 'Stop monitoring and wait for the port to close first.'),
 'read_first': ('Прочитайте цей канал із вибраного порту перед записом.', 'Read this channel from the selected port before writing.'),
 'channel': ('Вкажіть номер каналу від 1 до 1000.', 'Enter a channel number from 1 to 1000.'),
 'frequency': ('Введіть частоту в МГц, до 4 знаків після крапки або коми.', 'Enter a frequency in MHz with up to 4 decimal places.'),
 'band': ('Частота поза підтримуваними діапазонами PRO-2052.', 'Frequency is outside the supported PRO-2052 bands.'),
 'step': ('Частота не відповідає кроку цього діапазону:', 'Frequency does not match this band’s channel step:'),
 'response': ('Не вдалося підтвердити значення каналу. Запис не дозволено. Відповідь:', 'Channel value could not be confirmed. Writing is blocked. Response:'),
 'trunked': ('Це транкінговий канал. Ця версія записує лише звичайні частоти.', 'This is a trunking channel. This version only writes conventional frequencies.'),
 'same': ('Ця частота вже записана в каналі.', 'This frequency is already stored in the channel.'),
 'changed': ('Канал змінився після читання. Нічого не записано; прочитайте його знову.', 'The channel changed after reading. Nothing was written; read it again.'),
 'stale': ('Отримано неочікувані дані до запису. Запис скасовано; прочитайте канал знову.', 'Unexpected data arrived before writing. Write cancelled; read the channel again.'),
 'uncertain': ('Результат запису не підтверджено. Канал міг змінитися. Прочитайте його знову; автоматичного повтору немає.', 'Write result is unconfirmed. The channel may have changed. Read it again; no automatic retry is performed.'),
 'error': ('Операцію зупинено. Перевірте REMOTE, порт, швидкість і доступ до папки даних.', 'Operation stopped. Check REMOTE, port, baud rate and data-folder access.'),
 'port': ('Виберіть порт сканера і підтримувану швидкість.', 'Select a scanner port and a supported baud rate.'),
}

class ProgrammingPanel:
    def __init__(self, app, parent):
        self.app, self.parent = app, parent
        self.busy, self.thread, self.preview = False, None, None
        self.events = queue.Queue()
        self.inventory = None
        self.mapping_connection = None
        self.cancel_scan = threading.Event()
        self.only_duplicates = tk.BooleanVar(value=False)
        self.labels = []
        self.status_key, self.status_values = 'ready', {}
        self.channel = tk.StringVar(value='1')
        self.frequency = tk.StringVar()
        self.status = tk.StringVar()
        self.label(parent, 'intro').pack(anchor='w', pady=(4,8))
        form = ttk.Frame(parent); form.pack(anchor='w')
        self.label(form, 'channel_label').grid(row=0,column=0,sticky='w',padx=(0,12),pady=8)
        self.channel_input = ttk.Entry(form,textvariable=self.channel,width=14)
        self.channel_input.grid(row=0,column=1,sticky='w')
        self.read_button = self.button(form,'read',self.read)
        self.read_button.grid(row=0,column=2,padx=12)
        self.label(form,'frequency_label').grid(row=1,column=0,sticky='w',padx=(0,12),pady=8)
        self.frequency_input = ttk.Entry(form,textvariable=self.frequency,width=20)
        self.frequency_input.grid(row=1,column=1,sticky='w')
        self.write_button = self.button(form,'write',self.write)
        self.write_button.grid(row=1,column=2,padx=12)
        ttk.Label(parent,textvariable=self.status,wraplength=760,font=('Helvetica Neue',11)).pack(anchor='w',pady=8)
        self.label(parent,'limits').pack(anchor='w',pady=4)
        actions=ttk.Frame(parent); actions.pack(fill='x',pady=8)
        self.scan_button=self.button(actions,'read_all',self.read_all)
        self.scan_button.pack(side='left')
        self.cancel_button=self.button(actions,'cancel_read',self.cancel_scan.set)
        self.cancel_button.pack(side='left',padx=6);self.cancel_button.configure(state='disabled')
        # Address 000 = physical 1000 confirmed on this scanner by the user.
        from channel_editor import ChannelEditor
        self.tools_button=self.button(actions,'tools',lambda:ChannelEditor(self.app))
        self.tools_button.pack(side='left',padx=5)
        check=ttk.Checkbutton(actions,variable=self.only_duplicates,command=self.render_inventory)
        self.labels.append((check,'only_duplicates'));check.pack(side='left',padx=8)
        self.progress=ttk.Progressbar(parent,maximum=1000);self.progress.pack(fill='x')
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=6)
        self.table=ttk.Treeview(frame,columns=('channel','frequency','state','duplicates'),show='headings',height=8)
        for key,width in [('channel',80),('frequency',130),('state',110),('duplicates',400)]:
            self.table.column(key,width=width,minwidth=60,stretch=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        self.table.bind('<Double-1>',self.choose_channel)
        self.table.bind('<Return>',self.choose_channel)
        self.label(parent,'inventory_note').pack(anchor='w')
        self.retranslate()
        self.after_id = app.root.after(100,self.drain)

    def text(self,key,**values):
        language = self.app.language_ui.language
        return STRINGS[key][int(language=='en')].format(**values)

    def label(self,parent,key):
        widget=ttk.Label(parent,wraplength=760)
        self.labels.append((widget,key)); return widget

    def button(self,parent,key,command):
        widget=ttk.Button(parent,command=command)
        self.labels.append((widget,key)); return widget

    def retranslate(self):
        for widget,key in self.labels: widget.configure(text=self.text(key))
        self.app.notebook.tab(self.parent,text=self.text('title'))
        self.status.set(self.text(self.status_key,**self.status_values))
        for key in self.table['columns']:
            self.table.heading(key,text=self.text('table_'+key))
        self.render_inventory()

    def set_status(self,key,**values):
        self.status_key,self.status_values=key,values
        self.status.set(self.text(key,**values))

    def selection(self):
        if self.busy: return None
        if self.app.worker is not None:
            messagebox.showinfo(self.text('title'),self.text('stop'),parent=self.app.root)
            return None
        name=normalize_port(self.app.port.get())
        baud=self.app.baud.get()
        if not valid_port(name) or baud not in ('2400','4800','9600','19200'):
            raise protocol.ProgrammingError('port')
        return name,int(baud),protocol.channel_number(self.channel.get().strip())

    def show_error(self,exc):
        code=exc.code if isinstance(exc,protocol.ProgrammingError) else 'error'
        detail=exc.detail if isinstance(exc,protocol.ProgrammingError) else str(exc)
        self.set_status(code)
        messagebox.showerror(self.text('title'),self.text(code)+('\n\n'+detail if detail else ''),parent=self.app.root)

    def read(self):
        try:
            selected=self.selection()
            if selected:
                self.preview=None
                self.launch('read',selected)
        except Exception as exc: self.show_error(exc)

    def write(self):
        try:
            selected=self.selection()
            if not selected: return
            if not self.preview or self.preview[0]!=selected:
                raise protocol.ProgrammingError('read_first')
            if not self.inventory or not self.inventory.complete or (self.inventory.port,self.inventory.baud)!=selected[:2]:
                raise protocol.ProgrammingError('inventory_required')
            old=self.preview[1]
            digits=protocol.frequency_digits(self.frequency.get())
            duplicates=self.inventory.duplicates(digits,selected[2])
            if duplicates:
                raise protocol.ProgrammingError('duplicate',', '.join(self.inventory.label(n) for n in duplicates))
            if old.trunked: raise protocol.ProgrammingError('trunked')
            if old.digits==digits: raise protocol.ProgrammingError('same')
            name,baud,number=selected
            if not messagebox.askyesno(self.text('title'),self.text('confirm',channel=str(number or 1000),port=name,baud=baud,old=protocol.mhz(old.digits),new=protocol.mhz(digits)),parent=self.app.root,default='no'):
                return
            self.launch('write',selected,old,protocol.mhz(digits))
        except Exception as exc: self.show_error(exc)

    def launch(self,action,selected,old=None,frequency=None):
        if not self.app.save_connection(): return
        self.busy=True
        self.cancel_scan.clear()
        self.action=action
        self.set_status('reading' if action=='read' else 'writing')
        widgets=(self.scan_button,self.channel_input,self.frequency_input,self.read_button,self.write_button,
                 self.app.start_button,self.app.reconnect_button,self.app.ports,self.app.bauds,self.app.refresh_button)
        self.saved_states=[(w,w.cget('state')) for w in widgets]
        for w,state in self.saved_states: w.configure(state='disabled')
        if action in ('scan','batch','search'): self.cancel_button.configure(state='normal')
        log=self.app.data_dir/'logs'/f'programming-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.csv'
        self.app.log_path.set(str(log))
        self.thread=threading.Thread(target=self.run,args=(action,selected,log,old,frequency),daemon=False)
        self.thread.start()

    def run(self,action,selected,log,old,frequency):
        try:
            import serial
            name,baud,number=selected
            with serial.Serial(port=None,baudrate=baud,bytesize=8,parity='N',stopbits=1,
                               timeout=.1,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False) as port:
                port.dtr=False; port.rts=False; port.port=name; port.open()
                if action=='remote':
                    import remote_control
                    result=remote_control.execute(port,old['id'],old['parameter'],log,name,baud,old['reset'])
                elif action=='batch':
                    import channel_tools
                    result=channel_tools.apply_plan(port,old,frequency,self.app.data_dir,log,name,baud,self.cancel_scan,
                        lambda n,ch,backup:self.events.put(('written',selected,(n,ch,backup))))
                elif action=='search':
                    import frequency_search
                    frequency_search.run_search(port,name,baud,old['low'],old['high'],self.app.data_dir,log,self.cancel_scan,
                        lambda kind,data:self.events.put(('search_event',selected,(kind,data))),old['known'])
                    result=None
                elif action=='scan':
                    result=memory.read_all(port,name,baud,self.app.data_dir,log,self.cancel_scan,
                        lambda count,ch,address,error: self.events.put(('progress',selected,(count,ch,address,error))),
                        True)
                elif action=='map':
                    result=(memory.verify_last_channel(port,log,name,baud),None)
                elif action=='read':
                    result=(protocol.read_channel(port,number or 1000,log,name,baud),None)
                else:
                    result=protocol.program_channel(port,old,frequency,self.app.data_dir,log,name,baud)
            self.events.put(('result',selected,result))
        except Exception as exc:
            self.events.put(('error',selected,exc))

    def read_all(self):
        try:
            selected=self.selection()
            if not selected: return
            self.preview=None
            self.inventory=memory.Inventory(*selected[:2],confirmed_last=True)
            self.table.delete(*self.table.get_children())
            self.progress['value']=0
            self.launch('scan',selected)
        except Exception as exc: self.show_error(exc)

    def verify_last(self):
        try:
            selected=self.selection()
            if selected and messagebox.askyesno(self.text('title'),self.text('mapping_prompt'),parent=self.app.root,default='no'):
                self.launch('map',selected)
        except Exception as exc: self.show_error(exc)

    def render_inventory(self):
        self.table.delete(*self.table.get_children())
        if not self.inventory: return
        inv=self.inventory
        groups={}
        for address,ch in inv.records.items():
            if ch.digits!='00000000': groups.setdefault(ch.digits,[]).append(address)
        for address in [*range(1,1000),0]:
            ch=inv.records.get(address)
            others=[n for n in groups.get(ch.digits,[]) if n!=address] if ch else []
            if self.only_duplicates.get() and not others: continue
            state=self.text('empty' if ch.digits=='00000000' else 'stored') if ch else self.text('unread')
            self.table.insert('', 'end',iid=str(address),values=(inv.label(address),protocol.mhz(ch.digits) if ch else '—',state,', '.join(inv.label(n) for n in others)))

    def choose_channel(self,event=None):
        if self.busy or not self.inventory: return
        selected=self.table.selection()
        if not selected: return
        address=int(selected[0])
        self.channel.set(str(address or 1000))
        self.read()

    def drain(self):
        # Progress and final results are consumed on the Tk thread only.
        for _ in range(100):
            try: kind,selected,result=self.events.get_nowait()
            except queue.Empty: break
            if kind=='written':
                n,ch,backup=result
                self.inventory.records[n]=ch
                self.inventory.errors.pop(n,None)
                self.render_inventory()
            elif kind=='search_event':
                self.app.search.event(*result)
            elif kind=='progress':
                count,ch,address,error=result
                if ch: self.inventory.records[address]=ch
                if error: self.inventory.errors[address]=error
                self.progress['value']=count
                self.set_status('scan_progress',count=count)
                if count%25==0 or count==1000: self.render_inventory()
            else:
                self.pending_result=(kind,selected,result)
        if self.busy and self.thread and not self.thread.is_alive() and hasattr(self,'pending_result'):
            self.busy=False
            self.cancel_button.configure(state='disabled')
            for w,state in self.saved_states: w.configure(state=state)
            kind,selected,result=self.pending_result
            del self.pending_result
            if kind=='error':
                self.preview=None
                if self.action=='scan' and self.inventory:
                    self.inventory.cancelled=True
                if self.action=='batch' and self.inventory:
                    self.inventory.cancelled=True
                if self.action=='search': self.app.search.finished(result)
                if self.action=='remote': self.app.remote.finished(error=result)
                if self.action=='write' and self.inventory:
                    self.inventory.errors[selected[2]]=str(result)
                if not self.app.closing: self.show_error(result)
            elif self.action=='remote':
                self.app.remote.finished(result)
            elif self.action=='batch':
                self.set_status('batch_done',count=len(result))
                self.preview=None
                self.render_inventory()
            elif self.action=='search':
                self.app.search.finished()
            elif self.action=='scan':
                self.inventory=result
                self.render_inventory()
                self.inventory_status()
            elif self.action=='map':
                actual,backup=result
                self.mapping_connection=selected[:2]
                if self.inventory and (self.inventory.port,self.inventory.baud)==selected[:2]:
                    self.inventory.records[0]=actual
                    self.inventory.errors.pop(0,None)
                    self.inventory.confirmed_last=True
                    try:
                        memory.save_inventory(self.inventory,self.app.data_dir)
                        self.inventory_status()
                    except Exception as exc: self.show_error(exc)
                    self.render_inventory()
                else: self.set_status('mapped')
            else:
                actual,backup=result
                self.preview=(selected,actual)
                self.frequency.set(protocol.mhz(actual.digits))
                if self.inventory and (self.inventory.port,self.inventory.baud)==selected[:2]:
                    self.inventory.records[actual.number]=actual
                    self.inventory.errors.pop(actual.number,None)
                    self.render_inventory()
                if backup:
                    self.set_status('verified',channel=str(actual.number or 1000),frequency=protocol.mhz(actual.digits),backup=backup)
                else:
                    self.set_status('current',channel=str(actual.number or 1000),frequency=protocol.mhz(actual.digits))
        self.after_id=self.app.root.after(100,self.drain)

    def inventory_status(self):
        inv=self.inventory
        if inv.complete: self.set_status('scan_complete',path=Path(inv.path).name)
        else: self.set_status('scan_partial',count=len(inv.records),path=Path(inv.path).name)
