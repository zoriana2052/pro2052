"""Platform boundaries for desktop storage, serial names and instance locking."""
import os
from pathlib import Path
import re
import subprocess
import sys

def normalize_port(value):
    value=str(value).strip()
    return value.upper() if re.fullmatch(r'COM[1-9][0-9]*',value,re.I) else value

def valid_port(value):
    value=normalize_port(value)
    if sys.platform == 'win32':
        return bool(re.fullmatch(r'COM[1-9][0-9]*',value))
    if sys.platform == 'darwin':
        return bool(re.fullmatch(r'/dev/(?:cu|tty)\.[A-Za-z0-9_.-]+',value))
    return bool(re.fullmatch(r'/dev/tty(?:USB|ACM|S)[0-9]+',value))

def default_data_folder():
    if sys.platform == 'darwin':
        return Path.home()/'Library'/'Application Support'/'PRO2052'
    if sys.platform == 'win32':
        local=os.environ.get('LOCALAPPDATA')
        return (Path(local) if local else Path.home()/'AppData'/'Local')/'PRO2052'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'PRO2052'

def open_folder(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open',str(path)])

class InstanceLock:
    def __init__(self,path):
        self.file=open(path,'a+b')
        try:
            if sys.platform == 'win32':
                import msvcrt
                self.file.seek(0,2)
                if not self.file.tell():self.file.write(b'0');self.file.flush()
                self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Program already running / Програма вже запущена')

    def close(self):
        if self.file.closed:return
        if sys.platform == 'win32':
            import msvcrt
            self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
        self.file.close()
