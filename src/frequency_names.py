"""User labels keyed by exact frequency, independent of scanner settings."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox


def frequency_key(value):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError('Invalid frequency')
    return format(number.normalize(), 'f')


class FrequencyNames:
    def __init__(self, path):
        self.path = Path(path)
        self.names = {}
        self.load_error = None
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
                raise ValueError('Invalid names file')
            self.names = {frequency_key(k): v for k,v in data.items()}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, InvalidOperation) as exc:
            self.load_error = str(exc)

    def get(self, frequency):
        return self.names.get(frequency_key(frequency), '')

    def save(self, frequency, name):
        if self.load_error:
            raise ValueError(self.load_error)
        name = name.strip()
        if len(name) > 120 or any(ord(c) < 32 for c in name):
            raise ValueError('Name must be a single line, up to 120 characters')
        updated = dict(self.names)
        key = frequency_key(frequency)
        if name:
            updated[key] = name
        else:
            updated.pop(key, None)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.path)
        self.names = updated


class NameDialog(simpledialog.Dialog):
    def __init__(self, parent, frequency, current, translate):
        self.frequency, self.current, self.t = frequency, current, translate
        super().__init__(parent, title=translate('Назва частоти'))

    def body(self, master):
        ttk.Label(master, text=f'{self.frequency} MHz').pack(anchor='w', pady=(4,8))
        ttk.Label(master, text=self.t('Введіть назву. Порожнє поле видаляє назву.')).pack(anchor='w')
        self.entry = ttk.Entry(master, width=48)
        self.entry.pack(fill='x', pady=8)
        self.entry.insert(0, self.current)
        self.entry.select_range(0, 'end')
        return self.entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=self.t('Зберегти'), command=self.ok).pack(side='left', padx=5)
        ttk.Button(box, text=self.t('Скасувати'), command=self.cancel).pack(side='left', padx=5)
        box.pack(pady=8)
        self.bind('<Return>', self.ok)
        self.bind('<Escape>', self.cancel)

    def validate(self):
        value = self.entry.get().strip()
        if len(value)>120 or any(ord(c)<32 for c in value):
            messagebox.showerror(self.t('Назва частоти'), self.t('Назва має бути одним рядком до 120 символів.'), parent=self)
            return False
        return True

    def apply(self):
        self.result = self.entry.get().strip()


def ask_name(parent, frequency, current, translate):
    return NameDialog(parent, frequency, current, translate).result
