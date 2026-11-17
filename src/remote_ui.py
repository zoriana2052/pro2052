from platform_support import normalize_port, valid_port, open_folder
"""Front-panel controls and complete manual command catalog, one transaction at a time."""
from datetime import datetime
import re
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
import remote_control as remote
import inventory as memory

class RemotePanel:
    def __init__(self,app):
        self.app=app;self.panel=app.programming;self.labels=[]
        self.frame=ttk.Frame(app.notebook,padding=10);app.notebook.add(self.frame,text='Пульт')
        top=ttk.Frame(self.frame);top.pack(fill='x')
        for id,uk,en in [('get_MD','Режим','Mode'),('get_MA','Канал / частота','Channel / frequency'),('get_SQ','Шумоподавлювач','Squelch'),('get_SI','Інформація','Information')]:
            self.button(top,uk,en,lambda id=id:self.send(id)).pack(side='left',padx=3)
        self.button(top,'Банки та налаштування частоти…','Banks and tuning…',self.quick).pack(side='right',padx=3)
        self.state=tk.StringVar(value='—');ttk.Label(self.frame,textvariable=self.state,font=('Helvetica Neue',11),wraplength=920).pack(anchor='w',pady=8)
        body=ttk.Panedwindow(self.frame,orient='horizontal');body.pack(fill='both',expand=True)
        keys=ttk.Frame(body,padding=8);catalog=ttk.Frame(body,padding=8);body.add(keys,weight=1);body.add(catalog,weight=3)
        for i,key in enumerate(['SCAN','MANUAL','SEARCH','SERVICE','UP','DOWN','PRIORITY','LOCKOUT','DATA','DELAY','TRUNK','SHIFT']):
            a=remote.BY_ID['key_'+key]
            self.button(keys,a.uk,a.en,lambda id=a.id:self.send(id)).grid(row=i//2,column=i%2,sticky='ew',padx=2,pady=3)
        keypad=ttk.Frame(keys);keypad.grid(row=6,column=0,columnspan=2,pady=10)
        for i,digit in enumerate('123456789'):
            ttk.Button(keypad,text=digit,width=6,command=lambda d=digit:self.send('key_DIGIT',d)).grid(row=i//3,column=i%3,padx=2,pady=2)
        ttk.Button(keypad,text='.',width=6,command=lambda:self.send('key_CLEAR')).grid(row=3,column=0)
        ttk.Button(keypad,text='0',width=6,command=lambda:self.send('key_DIGIT','0')).grid(row=3,column=1)
        ttk.Button(keypad,text='E',width=6,command=lambda:self.send('key_ENTER')).grid(row=3,column=2)
        self.label(keys,'Це короткі натискання. Функція клавіші залежить від режиму сканера.','These are short presses. A key’s effect depends on the scanner mode.',270).grid(row=7,column=0,columnspan=2,pady=5)
        self.label(keys,'Гучність і поріг SQUELCH регулюються фізичними ручками. Довге натискання та перемикання REMOTE виконуються на сканері.','Volume and SQUELCH threshold use physical knobs. Long presses and REMOTE switching are performed on the scanner.',270).grid(row=8,column=0,columnspan=2,pady=5)
        self.filter=tk.StringVar();filterbar=ttk.Frame(catalog);filterbar.pack(fill='x')
        self.label(filterbar,'Пошук функції','Find function').pack(side='left')
        ttk.Entry(filterbar,textvariable=self.filter).pack(side='left',fill='x',expand=True,padx=6)
        self.filter.trace_add('write',lambda *args:self.render())
        tableframe=ttk.Frame(catalog);tableframe.pack(fill='both',expand=True,pady=7)
        self.table=ttk.Treeview(tableframe,columns=('name','command'),show='headings',selectmode='browse',height=10)
        self.table.column('name',width=320);self.table.column('command',width=110)
        scroll=ttk.Scrollbar(tableframe,command=self.table.yview);self.table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        self.table.bind('<<TreeviewSelect>>',self.select)
        self.hint=tk.StringVar();ttk.Label(catalog,textvariable=self.hint,wraplength=560).pack(anchor='w')
        self.parameter=tk.StringVar();ttk.Entry(catalog,textvariable=self.parameter).pack(fill='x',pady=6)
        self.advanced=tk.BooleanVar(value=False)
        check=ttk.Checkbutton(catalog,variable=self.advanced);self.labels.append((check,'Кодування розширених параметрів мені відоме','I know the encoding of these advanced parameters'));check.pack(anchor='w')
        self.button(catalog,'Переглянути / виконати','Review / execute',self.execute_selected).pack(anchor='w',pady=6)
        self.label(self.frame,'Результати — останні відповіді, не постійний дисплей сканера. OK означає прийняття команди, а не перевірку всіх налаштувань.','Results are last responses, not a continuous scanner display. OK acknowledges a command; it does not verify all settings.').pack(anchor='w',pady=5)
        self.output=tk.Text(self.frame,height=5,state='disabled',font=('Menlo',10));self.output.pack(fill='x')
        self.label(self.frame,'Завершіть операцію та вимкніть REMOTE для керування кнопками сканера.','Finish the operation and turn REMOTE off to use scanner buttons.').pack(anchor='w',pady=5)
        self.retranslate()

    def t(self,uk,en):return en if self.app.language_ui.language=='en' else uk
    def label(self,parent,uk,en,width=920):
        w=ttk.Label(parent,wraplength=width);self.labels.append((w,uk,en));return w
    def button(self,parent,uk,en,command):
        w=ttk.Button(parent,command=command);self.labels.append((w,uk,en));return w
    def retranslate(self):
        self.app.notebook.tab(self.frame,text=self.t('Пульт і налаштування','Controls and settings'))
        for w,uk,en in self.labels:w.configure(text=self.t(uk,en))
        self.table.heading('name',text=self.t('Функція','Function'));self.table.heading('command',text=self.t('Команда','Command'))
        self.render()
    def render(self):
        selected=self.table.selection();self.table.delete(*self.table.get_children())
        query=self.filter.get().casefold()
        for a in remote.ACTIONS:
            if query and query not in (a.uk+' '+a.en+' '+a.prefix).casefold():continue
            self.table.insert('','end',iid=a.id,values=(self.t(a.uk,a.en),a.prefix+('…' if a.pattern else '')))
        if selected and self.table.exists(selected[0]):self.table.selection_set(selected)
    def select(self,event=None):
        rows=self.table.selection()
        if not rows:return
        a=remote.BY_ID[rows[0]];self.parameter.set('');self.advanced.set(False)
        self.hint.set(self.t('Параметри: ','Parameters: ')+(a.hint or '—')+self.t(' | Мануал, стор. ',' | Manual p. ')+str(a.page))
    def execute_selected(self):
        rows=self.table.selection()
        if rows:self.send(rows[0],self.parameter.get())
    def send(self,id,parameter=''):
        try:
            if self.panel.busy or self.app.worker is not None:
                raise ValueError(self.t('Спочатку зупиніть поточне опитування або дочекайтеся завершення команди.','Stop current polling or wait for the command to finish first.'))
            name=normalize_port(self.app.port.get());baud=self.app.baud.get()
            if not valid_port(name) or baud not in ('2400','4800','9600','19200'):raise ValueError('COM / baud')
            command=remote.build(id,parameter);a=remote.BY_ID[id]
            if id in ('talkgroup','trunk_bank','set_ic','get_pi','set_pi') and not self.advanced.get():
                raise ValueError(self.t('Мануал не пояснює повністю кодування цих параметрів. Не вгадуйте значення; підтвердьте, що знаєте формат для свого пристрою.','The manual does not fully define these parameter encodings. Do not guess values; confirm you know the format for your device.'))
            reset=False
            if id=='reset':
                inv=self.panel.inventory
                if not inv or not inv.complete or (inv.port,inv.baud)!=(name,int(baud)):raise ValueError(self.t('Перед очищенням прочитайте всі канали поточного сканера.','Read all channels from this scanner before clearing memory.'))
                backup=memory.save_inventory(inv,self.app.data_dir)
                prompt=self.t('Це видалить ВСЮ запрограмовану пам’ять сканера. Копія частот не містить усіх ID і налаштувань.\nКопія: ','This clears ALL programmed scanner memory. A frequency backup does not contain all IDs and settings.\nBackup: ')+str(backup)+'\n\n'+self.t('Для виконання введіть CLEAR MEMORY:','Type CLEAR MEMORY to execute:')
                reset=simpledialog.askstring(self.t(a.uk,a.en),prompt,parent=self.app.root)=='CLEAR MEMORY'
                if not reset:return
            elif a.mutation and (not id.startswith('key_') or id=='key_ENTER'):
                prompt=self.t(a.uk,a.en)+'\n'+name+' / '+baud+'\n\n'+command+'\n\n'+self.t('Виконати? Пам’ять або режим можуть змінитися; автоматичного відкату немає.','Execute? Memory or mode may change; there is no automatic rollback.')
                if not messagebox.askyesno(self.t('Підтвердження','Confirm'),prompt,parent=self.app.root,default='no'):return
            if a.memory and self.panel.inventory:
                self.panel.inventory.cancelled=True;self.panel.preview=None
            self.state.set(self.t('Виконується: ','Executing: ')+command)
            self.panel.launch('remote',(name,int(baud),1),dict(id=id,parameter=parameter,reset=reset))
        except Exception as exc:messagebox.showerror(self.t('Пульт','Controls'),str(exc),parent=self.app.root)
    def quick(self):
        win=tk.Toplevel(self.app.root);win.title(self.t('Банки та налаштування','Banks and tuning'));win.geometry('660x520')
        main=ttk.Frame(win,padding=14);main.pack(fill='both',expand=True)
        ttk.Label(main,text=self.t('Канал 1–1000','Channel 1–1000')).pack(anchor='w')
        row=ttk.Frame(main);row.pack(fill='x',pady=6)
        channel=tk.StringVar(value='1');ttk.Entry(row,textvariable=channel,width=12).pack(side='left')
        ttk.Button(row,text=self.t('Перейти','Go'),command=lambda:self.send('go_channel',channel.get())).pack(side='left',padx=6)
        ttk.Label(main,text=self.t('Частота, МГц — налаштування без запису каналу','Frequency MHz — tune without writing a channel')).pack(anchor='w')
        row=ttk.Frame(main);row.pack(fill='x',pady=6)
        freq=tk.StringVar();ttk.Entry(row,textvariable=freq,width=16).pack(side='left')
        ttk.Button(row,text=self.t('Налаштувати','Tune'),command=lambda:self.send('freq_RF',freq.get())).pack(side='left',padx=6)
        ttk.Label(main,text=self.t('Виберіть банки для сканування. Позначки не є прочитаним станом.','Choose scan banks. Checkboxes do not represent readback state.'),wraplength=600).pack(anchor='w',pady=8)
        grid=ttk.Frame(main);grid.pack(anchor='w')
        banks=[]
        for n in range(20):
            var=tk.BooleanVar(value=False);banks.append(var)
            ttk.Checkbutton(grid,text=str(n+1),variable=var).grid(row=n//5,column=n%5,padx=10,pady=4)
        ttk.Button(main,text=self.t('Застосувати вибрані банки','Apply selected banks'),command=lambda:self.send('set_banks',''.join(chr(65+n) for n,var in enumerate(banks) if var.get()))).pack(anchor='w',pady=8)
        ttk.Button(main,text=self.t('Прочитати активні банки','Read active banks'),command=lambda:self.send('get_SB')).pack(anchor='w')
        ttk.Label(main,text=self.t('Пріоритетний канал: банк (1–20), канал (1–1000)','Priority channel: bank (1–20), channel (1–1000)')).pack(anchor='w',pady=8)
        row=ttk.Frame(main);row.pack(fill='x')
        bank=tk.StringVar(value='1');priority=tk.StringVar(value='1')
        ttk.Combobox(row,textvariable=bank,values=[str(n) for n in range(1,21)],state='readonly',width=5).pack(side='left')
        ttk.Entry(row,textvariable=priority,width=8).pack(side='left',padx=5)
        def set_priority():
            try:
                import programming
                number=programming.channel_number(priority.get())
                self.send('set_priority',chr(64+int(bank.get()))+f'{number:03d}')
            except Exception as exc:messagebox.showerror('Priority',str(exc),parent=win)
        ttk.Button(row,text=self.t('Задати','Set'),command=set_priority).pack(side='left')
        ttk.Button(row,text=self.t('Прочитати','Read'),command=lambda:self.send('get_priority',chr(64+int(bank.get())))).pack(side='left',padx=5)

    def finished(self,rows=None,error=None):
        if error:
            self.state.set(self.t('Помилка. Результат зміни може бути невідомим: ','Error. The effect of a change may be unknown: ')+str(error));return
        self.output.configure(state='normal')
        for command,raw in rows:
            text=raw.decode('ascii',errors='backslashreplace').strip()
            self.output.insert('end',f'{datetime.now():%H:%M:%S} {command} → {raw!r}\n')
            if command=='MD' and re.fullmatch(r'MD[0-9]{2}',text):
                number=int(text[2:]);self.state.set(text+' — '+(remote.MODE_NAMES[number] if number<len(remote.MODE_NAMES) else '?'))
            elif raw==b'OK\r':self.state.set(self.t('Команду прийнято. Звірте налаштування за відповіддю читання або на сканері.','Command acknowledged. Check readback or the scanner display.'))
            elif raw.strip() in (b'NG',b'ERR',b'ORER') or not raw.endswith(b'\r') or raw.strip()==command.encode():self.state.set(self.t('Команду відхилено або результат не підтверджено: ','Rejected or unconfirmed result: ')+repr(raw))
            else:self.state.set(command+' → '+text)
        lines=int(self.output.index('end-1c').split('.')[0])
        if lines>150:self.output.delete('1.0',f'{lines-150}.0')
        self.output.see('end');self.output.configure(state='disabled')
