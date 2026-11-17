"""Packaged desktop entrypoint, logging and isolated no-hardware self-test."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import traceback
import tkinter as tk
from tkinter import messagebox
from app_storage import VERSION, data_folder, prepare_data

from platform_support import InstanceLock

def configure_window_icon(root):
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PRO2052.Desktop.Scanner')
    root._app_icon = tk.PhotoImage(file=str(Path(__file__).resolve().parent / 'scanner.png'))
    root.iconphoto(True, root._app_icon)


def self_test(destination):
    """No COM ports are opened. Uses isolated data next to the report."""
    from window import App
    from history import HistoryWindow
    from serial.tools import list_ports
    report = {'version':VERSION, 'frozen':bool(getattr(sys,'frozen',False))}
    root = None
    try:
        list(list_ports.comports())
        root = tk.Tk(); root.withdraw(); configure_window_icon(root)
        app = App(root, destination.parent / 'self-test-data')
        app.language_ui.language='en'; app.language_ui.apply()
        assert app.start_button.cget('text') == 'Start'
        assert app.notebook.tab(1, 'text') == 'Channel programming'
        assert app.programming.read_button.cget('text') == 'Read channel'
        app.notebook.select(1)
        root.update_idletasks()
        assert app.programming.write_button.winfo_reqwidth() > 0
        import inventory as memory
        import programming as protocol
        inv=memory.Inventory('COM5',19200,True,{i:protocol.Channel(i,'00000000',b'F00000000\r') for i in range(1000)})
        inv.records[22]=protocol.Channel(22,'04353750',b'F04353750\r')
        inv.records[198]=protocol.Channel(198,'04353750',b'F04353750\r')
        app.programming.inventory=inv
        app.programming.only_duplicates.set(True)
        app.programming.render_inventory()
        assert len(app.programming.table.get_children())==2
        assert app.programming.table.set('198','duplicates')=='022'
        app.notebook.select(0)
        for second in (0,2):
            app.events.put(('row',dict(event='activity_observation',
                local=f'2026-10-26T06:00:{second:02d}-04:00',frequency_mhz='450.2250',note='Channel 022')))
        app.drain(); root.update_idletasks()
        assert len(app.tree.get_children()) == 1
        assert app.tree.set(app.tree.get_children()[0],'samples') == '2'
        app.port.set('COM5' if sys.platform == 'win32' else '/dev/cu.usbserial-TEST'); app.baud.set('19200'); app.pace.set('Faster')
        assert app.save_connection()
        from channel_editor import ChannelEditor
        from channel_tools import load_file
        editor=ChannelEditor(app);editor.top.withdraw()
        editor.changes[0]='04502250';editor.refresh()
        assert editor.table.set('0','channel')=='1000'
        assert editor.table.set('0','new')=='450.2250'
        editor.top.destroy()
        example=app.data_dir/'self-test-import.csv'
        example.write_text('channel,frequency_mhz\n1000,450.2250\n',encoding='utf-8')
        assert load_file(example)=={0:'04502250'}
        assert not hasattr(app.programming,'mapping_button')
        assert app.notebook.tab(app.search.frame,'text')=='Frequency search'
        assert app.notebook.tab(app.remote.frame,'text')=='Controls and settings'
        import remote_control
        assert len(app.remote.table.get_children())==len(remote_control.ACTIONS)
        app.remote.finished([('MD',b'MD01\r')])
        assert 'Manual' in app.remote.state.get()
        app.search.event('hit',('04353750','2026-10-26T12:00:00-04:00','new'))
        assert len(app.search.table.get_children())==1
        history = HistoryWindow(app); history.top.withdraw()
        history.daily=[dict(day='2026-10-26',frequency='450.2250',first='first',last='last',samples=2,periods=1)]
        history.view.current(1); history.apply()
        assert len(history.tree.get_children()) == 1
        history.close()
        report.update(ok=True, tkinter=tk.TkVersion, checks=['UI startup','serial enumeration','English UI','grouped observations','saved connection','daily history','programming tab','inventory duplicates filter','table editor','CSV import','search UI','channel 1000 without test button','remote catalog and mode display'])
    except Exception:
        report.update(ok=False,error=traceback.format_exc())
    finally:
        if root is not None: root.destroy()
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report.get('ok') else 1


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        raise SystemExit(self_test(Path(sys.argv[2]).resolve()))
    root=tk.Tk(); root.withdraw(); configure_window_icon(root)
    lock=None
    try:
        folder=prepare_data(data_folder())
        lock=InstanceLock(folder/'instance.lock')
        handler=RotatingFileHandler(folder/'application.log',maxBytes=1000000,backupCount=3,encoding='utf-8')
        logging.basicConfig(level=logging.INFO,handlers=[handler])
        logging.info('Starting PRO-2052 %s',VERSION)
        if sys.stdout is None: sys.stdout=open(os.devnull,'w')
        if sys.stderr is None: sys.stderr=open(os.devnull,'w')
        def callback_error(kind,value,tb):
            logging.error('UI callback failed',exc_info=(kind,value,tb))
            messagebox.showerror('PRO-2052','Unexpected error / Неочікувана помилка\n'+str(value)+'\n'+str(folder/'application.log'),parent=root)
        root.report_callback_exception=callback_error
        from window import App
        App(root,folder)
        root.deiconify()
        root.mainloop()
    except Exception as exc:
        logging.exception('Application startup failed')
        messagebox.showerror('PRO-2052',str(exc),parent=root)
        root.destroy()
    finally:
        if lock: lock.close()

if __name__=='__main__': main()
