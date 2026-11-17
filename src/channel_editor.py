from platform_support import normalize_port, valid_port, open_folder
"""Reviewable table editor and offline snapshot comparison."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import channel_tools as plans
import programming as p

class ChannelEditor:
    def __init__(self,app):
        self.app=app;self.panel=app.programming;self.changes={};self.entry=None;self.free_cursor=1
        self.en=app.language_ui.language=='en'
        self.top=tk.Toplevel(app.root);self.top.title(self.t('Редактор каналів','Channel editor'))
        self.top.geometry('1050x670');self.top.minsize(850,500)
        self.status=tk.StringVar()
        bar=ttk.Frame(self.top,padding=10);bar.pack(fill='x')
        for uk,en,cmd in [('Імпорт CSV','Import CSV',self.import_csv),('Відновити з копії','Restore backup',self.restore),('Вільний канал','Empty channel',self.empty),('Порівняти знімки','Compare snapshots',self.compare_files)]:
            ttk.Button(bar,text=self.t(uk,en),command=cmd).pack(side='left',padx=3)
        ttk.Label(self.top,text=self.t('Двічі натисніть клітинку «Нова частота». Enter — додати зміну, Esc — скасувати. 0 — очистити канал.','Double-click New frequency. Enter stages the change; Esc cancels. 0 clears the channel.'),wraplength=950).pack(anchor='w',padx=14)
        frame=ttk.Frame(self.top,padding=10);frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(frame,columns=('channel','old','new','name'),show='headings',selectmode='extended')
        for key,uk,en,width in [('channel','Канал','Channel',80),('old','Зараз, МГц','Current MHz',170),('new','Нова частота, МГц','New frequency MHz',200),('name','Назва','Name',350)]:
            self.table.heading(key,text=self.t(uk,en));self.table.column(key,width=width)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.table.pack(fill='both',expand=True)
        self.table.tag_configure('changed',background='#fff2c6')
        self.table.bind('<Double-1>',self.edit)
        footer=ttk.Frame(self.top,padding=10);footer.pack(fill='x')
        ttk.Button(footer,text=self.t('Перегляд вибраних змін','Review selected changes'),command=self.review).pack(side='left')
        ttk.Button(footer,text=self.t('Вибрати всі зміни','Select all changes'),command=lambda:self.table.selection_set([str(n) for n in self.changes])).pack(side='left',padx=6)
        ttk.Button(footer,text=self.t('Скинути вибрані зміни','Discard selected changes'),command=self.discard).pack(side='left')
        ttk.Label(self.top,textvariable=self.status,wraplength=980).pack(anchor='w',padx=14,pady=8)
        self.refresh()

    def t(self,uk,en):return en if self.en else uk

    def ready(self):
        if self.panel.busy or self.app.worker is not None:raise ValueError(self.t('Спочатку завершіть поточну операцію.','Finish the current operation first.'))
        inv=self.panel.inventory
        if not inv or not inv.complete or (inv.port,str(inv.baud))!=(normalize_port(self.app.port.get()),self.app.baud.get()):
            raise ValueError(self.t('Спочатку прочитайте всі канали з поточного порту.','Read all channels from the current port first.'))
        return inv

    def error(self,exc):messagebox.showerror(self.top.title(),str(exc),parent=self.top)

    def refresh(self):
        self.table.delete(*self.table.get_children())
        inv=self.panel.inventory
        if inv:
            for n,ch in sorted(inv.records.items(),key=lambda item:item[0] or 1000):
                self.table.insert('','end',iid=str(n),values=(plans.label(n),p.mhz(ch.digits),p.mhz(self.changes[n]) if n in self.changes else '',self.app.names.get(p.mhz(ch.digits)) if ch.digits!='00000000' else ''),tags=('changed',) if n in self.changes else ())
        self.status.set(self.t('Підготовлено змін: ','Staged changes: ')+str(len(self.changes)))

    def edit(self,event):
        try:
            self.ready()
            row=self.table.identify_row(event.y);column=self.table.identify_column(event.x)
            if not row or column!='#3':return
            if self.entry:self.entry.destroy()
            x,y,w,h=self.table.bbox(row,'new');entry=ttk.Entry(self.table)
            self.entry=entry;entry.place(x=x,y=y,width=w,height=h)
            entry.insert(0,self.table.set(row,'new') or self.table.set(row,'old'));entry.select_range(0,'end');entry.focus_set()
            def save(event=None):
                try:
                    self.ready();n=int(row);value=plans.digits(entry.get())
                    if value==self.panel.inventory.records[n].digits:self.changes.pop(n,None)
                    else:self.changes[n]=value
                    entry.destroy();self.entry=None;self.refresh();self.table.selection_set(row);self.table.see(row)
                except Exception as exc:self.error(exc)
            entry.bind('<Return>',save);entry.bind('<Escape>',lambda e:entry.destroy())
        except Exception as exc:self.error(exc)

    def stage_file(self,restore=False):
        try:
            inv=self.ready()
            path=filedialog.askopenfilename(parent=self.top,filetypes=[('CSV / JSON','*.csv *.json')])
            if not path:return
            start=1
            if not restore:
                start=simpledialog.askinteger(self.top.title(),self.t('Починати пошук вільних каналів з номера (для CSV без channel):','Start assigning empty channels at (for CSV without channel):'),initialvalue=1,minvalue=1,maxvalue=1000,parent=self.top)
                if start is None:return
            loaded=plans.load_file(path,inv,start,self.changes)
            proposed={**self.changes,**loaded}
            # Parse the entire file before changing UI state; conflicts are checked in review.
            self.changes={n:v for n,v in proposed.items() if inv.records[n].digits!=v}
            self.refresh();self.table.selection_set([str(n) for n in self.changes])
            self.status.set(self.t('Файл завантажено лише в чергу змін. Перегляньте й виберіть потрібні рядки.','File staged only. Review and select the desired rows.'))
        except Exception as exc:self.error(exc)

    def import_csv(self):self.stage_file(False)
    def restore(self):self.stage_file(True)

    def empty(self):
        try:
            inv=self.ready();n=plans.next_empty(inv,start=self.free_cursor,reserved=self.changes)
            self.free_cursor=(n or 1000)+1
            if self.free_cursor>1000:self.free_cursor=1
            row=str(n);self.table.selection_set(row);self.table.see(row)
            self.status.set(self.t('Вільний канал: ','Empty channel: ')+plans.label(n))
        except Exception as exc:self.error(exc)

    def discard(self):
        if self.panel.busy:return
        for row in self.table.selection():self.changes.pop(int(row),None)
        self.refresh()

    def review(self):
        try:
            inv=self.ready()
            selected={int(row):self.changes[int(row)] for row in self.table.selection() if int(row) in self.changes}
            plan=plans.validate_plan(inv,selected)
            if not plan:raise ValueError(self.t('Виберіть підготовлені зміни.','Select staged changes.'))
            dialog=tk.Toplevel(self.top);dialog.title(self.t('Підтвердження запису','Confirm write'));dialog.geometry('650x480');dialog.transient(self.top);dialog.grab_set()
            ttk.Label(dialog,text=self.t('Буде записано лише ці рядки. 0.0000 означає очищення.','Only these rows will be written. 0.0000 means clearing.'),wraplength=620).pack(pady=10)
            tree=ttk.Treeview(dialog,columns=('channel','old','new'),show='headings')
            for key,title in [('channel',self.t('Канал','Channel')),('old',self.t('Було','Before')),('new',self.t('Буде','After'))]:tree.heading(key,text=title);tree.column(key,width=160)
            for n,v in plan.items():tree.insert('','end',values=(plans.label(n),p.mhz(inv.records[n].digits),p.mhz(v)))
            tree.pack(fill='both',expand=True,padx=10)
            ttk.Label(dialog,text=self.t('Після операції вимкніть REMOTE для керування кнопками.','After the operation, turn REMOTE off to use scanner buttons.')).pack(pady=8)
            def commit():
                try:
                    self.ready();plans.validate_plan(inv,plan)
                    dialog.destroy()
                    self.panel.launch('batch',(inv.port,inv.baud,1),inv,plan)
                    self.status.set(self.t('Запис виконується. Результат — у головному вікні.','Writing. See the main window for results.'))
                    self.top.after(150,lambda:self.await_batch(plan))
                except Exception as exc:self.error(exc)
            ttk.Button(dialog,text=self.t('Записати вибрані','Write selected'),command=commit).pack(side='left',padx=15,pady=10)
            ttk.Button(dialog,text=self.t('Скасувати','Cancel'),command=dialog.destroy).pack(side='right',padx=15,pady=10)
        except Exception as exc:self.error(exc)

    def await_batch(self,plan):
        if not self.top.winfo_exists():return
        if self.panel.busy:self.top.after(150,lambda:self.await_batch(plan));return
        for n,v in plan.items():
            if self.panel.inventory.records[n].digits==v:self.changes.pop(n,None)
        self.refresh()

    def compare_files(self):
        try:
            a=filedialog.askopenfilename(parent=self.top,title=self.t('Перший знімок','First snapshot'),filetypes=[('CSV','*.csv')])
            if not a:return
            b=filedialog.askopenfilename(parent=self.top,title=self.t('Другий знімок','Second snapshot'),filetypes=[('CSV','*.csv')])
            if not b:return
            differences=plans.compare(plans.load_file(a),plans.load_file(b))
            win=tk.Toplevel(self.top);win.title(self.t('Порівняння знімків','Snapshot comparison'));win.geometry('850x500')
            table=ttk.Treeview(win,columns=('channel','before','after','kind'),show='headings')
            for key,title in [('channel',self.t('Канал','Channel')),('before',Path(a).name),('after',Path(b).name),('kind',self.t('Зміна','Change'))]:table.heading(key,text=title)
            labels={'added':self.t('Додано','Added'),'cleared':self.t('Очищено','Cleared'),'changed':self.t('Змінено','Changed'),'unknown':self.t('Немає даних','Unknown')}
            for n,old,new,kind in differences:table.insert('','end',values=(plans.label(n),p.mhz(old) if old else '—',p.mhz(new) if new else '—',labels[kind]))
            scroll=ttk.Scrollbar(win,command=table.yview);table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');table.pack(fill='both',expand=True)
            ttk.Label(win,text=self.t('Відмінностей: ','Differences: ')+str(len(differences))).pack()
        except Exception as exc:self.error(exc)
