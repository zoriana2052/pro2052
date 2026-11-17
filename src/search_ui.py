import tkinter as tk
from tkinter import ttk,messagebox,filedialog
import csv
from pathlib import Path
import frequency_search as search
import programming as p

class SearchPanel:
    def __init__(self,app):
        self.app=app;self.panel=app.programming;self.hits={};self.labels=[]
        self.frame=ttk.Frame(app.notebook,padding=14);app.notebook.add(self.frame,text='Пошук частот')
        self.low=tk.StringVar(value='430.0000');self.high=tk.StringVar(value='440.0000');self.status=tk.StringVar()
        self.label('Пошук сигналів у діапазоні. Межі пошуку на сканері зміняться; попередні збережуться у data/search-backups.','Search for signals in a range. Scanner search limits will change; previous limits are saved in data/search-backups.').pack(anchor='w',pady=10)
        controls=ttk.Frame(self.frame);controls.pack(fill='x')
        for uk,en,var in [('Від, МГц','From MHz',self.low),('До, МГц','To MHz',self.high)]:
            label=ttk.Label(controls);self.labels.append((label,uk,en));label.pack(side='left',padx=4)
            ttk.Entry(controls,textvariable=var,width=13).pack(side='left',padx=4)
        self.start=ttk.Button(controls,command=self.begin);self.labels.append((self.start,'Почати пошук','Start search'));self.start.pack(side='left',padx=8)
        self.stop=ttk.Button(controls,command=self.panel.cancel_scan.set,state='disabled');self.labels.append((self.stop,'Зупинити пошук','Stop search'));self.stop.pack(side='left')
        ttk.Label(self.frame,textvariable=self.status,wraplength=800).pack(anchor='w',pady=12)
        frame=ttk.Frame(self.frame);frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(frame,columns=('frequency','first','last','count','kind'),show='headings')
        for key,width in [('frequency',130),('first',230),('last',230),('count',80),('kind',130)]:self.table.column(key,width=width)
        scroll=ttk.Scrollbar(frame,command=self.table.yview);self.table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        button=ttk.Button(self.frame,command=self.stage);self.labels.append((button,'Додати вибрану частоту до черги запису','Stage selected frequency in an empty channel'));button.pack(anchor='w',pady=10)
        export=ttk.Button(self.frame,command=self.export);self.labels.append((export,'Експорт знахідок CSV','Export findings CSV'));export.pack(anchor='w',pady=(0,8))
        self.label('Знахідка — спостереження сигналу, не гарантовано голос. Частоти не записуються автоматично. Якщо MA не підтвердить частоту, вона не потрапить до списку.','A finding is a signal observation, not necessarily voice. No automatic channel writes. Frequencies are listed only when MA confirms them.').pack(anchor='w')
        self.label('Після зупинки вимкніть REMOTE для керування кнопками сканера.','After stopping, turn REMOTE off to use scanner buttons.').pack(anchor='w',pady=8)
        self.retranslate()

    def t(self,uk,en):return en if self.app.language_ui.language=='en' else uk
    def label(self,uk,en):
        label=ttk.Label(self.frame,wraplength=850);self.labels.append((label,uk,en));return label
    def retranslate(self):
        self.app.notebook.tab(self.frame,text=self.t('Пошук частот','Frequency search'))
        for label,uk,en in self.labels:label.configure(text=self.t(uk,en))
        for key,uk,en in [('frequency','Частота, МГц','Frequency MHz'),('first','Перша знахідка','First found'),('last','Остання знахідка','Last found'),('count','Зразків','Samples'),('kind','У пам’яті','In memory')]:self.table.heading(key,text=self.t(uk,en))
        self.render()

    def begin(self):
        try:
            selected=self.panel.selection()
            if not selected:return
            search.bounds(self.low.get(),self.high.get())
            if not messagebox.askyesno(self.t('Пошук','Search'),self.t('Запустити пошук? Сканер змінить межі й режим. Після зупинки перейде в MANUAL.','Start search? Scanner limits and mode will change. Stopping returns to MANUAL.'),parent=self.app.root,default='no'):return
            self.hits={};self.render()
            inv=self.panel.inventory
            known={c.digits for c in inv.records.values() if c.digits!='00000000'} if inv and inv.complete and (inv.port,inv.baud)==selected[:2] else None
            self.panel.launch('search',selected,dict(low=self.low.get(),high=self.high.get(),known=known))
            if self.panel.busy:
                self.start.configure(state='disabled');self.stop.configure(state='normal')
                self.status.set(self.t('Пошук запускається…','Starting search…'))
        except Exception as exc:messagebox.showerror(self.t('Пошук','Search'),str(exc),parent=self.app.root)

    def event(self,kind,data):
        if kind=='notice':self.status.set(data);return
        value,stamp,membership=data
        row=self.hits.setdefault(value,dict(first=stamp,last=stamp,count=0,kind=membership))
        row['last']=stamp;row['count']+=1
        self.render();self.status.set(self.t('Знайдено частот: ','Frequencies found: ')+str(len(self.hits)))

    def render(self):
        self.table.delete(*self.table.get_children())
        labels={'new':self.t('Нова','New'),'known':self.t('Уже є','Already stored'),'unknown':self.t('Не перевірено','Not checked')}
        for value,row in sorted(self.hits.items()):self.table.insert('','end',iid=value,values=(p.mhz(value),row['first'],row['last'],row['count'],labels[row['kind']]))

    def finished(self,error=None):
        self.start.configure(state='normal');self.stop.configure(state='disabled')
        self.status.set((str(error)+'\n' if error else '')+self.t('Завершено. Для кнопок сканера вимкніть REMOTE. Журнал: ','Finished. Turn REMOTE off to use scanner buttons. Log: ')+Path(self.app.log_path.get()).name)

    def export(self):
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if not path:return
        try:
            with open(path,'w',encoding='utf-8-sig',newline='') as file:
                writer=csv.writer(file);writer.writerow(['frequency_mhz','first','last','samples','membership'])
                for value,row in sorted(self.hits.items()):writer.writerow([p.mhz(value),row['first'],row['last'],row['count'],row['kind']])
        except OSError as exc:messagebox.showerror('CSV',str(exc),parent=self.app.root)

    def stage(self):
        try:
            if self.panel.busy:raise ValueError(self.t('Спочатку зупиніть пошук.','Stop search first.'))
            rows=self.table.selection()
            if not rows:return
            from channel_editor import ChannelEditor
            from channel_tools import next_empty
            editor=ChannelEditor(self.app);inv=editor.ready();value=rows[0]
            if inv.duplicates(value):editor.top.destroy();raise ValueError(self.t('Частота вже є у пам’яті.','Frequency already stored.'))
            n=next_empty(inv);editor.changes[n]=value;editor.refresh();editor.table.selection_set(str(n));editor.table.see(str(n))
        except Exception as exc:messagebox.showerror(self.t('Пошук','Search'),str(exc),parent=self.app.root)
