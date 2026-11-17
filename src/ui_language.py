"""UI-only translations; serial commands and CSV format remain unchanged."""
import json
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

TEXT = {
'Імпортувати дані…': 'Import data…',
'Імпорт даних': 'Data import',
'Спочатку зупиніть роботу зі сканером.': 'Stop scanner operations first.',
'Виберіть папку старої програми або її папку data': 'Select the old program folder or its data folder',
'Скопійовано файлів: ': 'Files copied: ',
'Наявні файли не замінено. Перезапустіть програму, щоб застосувати налаштування.': 'Existing files were not replaced. Restart to apply imported settings.',

'Після завершення вимкніть REMOTE, щоб користуватися кнопками сканера.': 'When finished, turn REMOTE off to use scanner buttons.',
'Експорт результатів CSV': 'Export results CSV',
'Підключитися знову': 'Reconnect',
'Папка даних': 'Data folder',
'Налаштування': 'Settings',
'Не вдалося зберегти налаштування.': 'Could not save settings.',
'Збережений порт недоступний. Виберіть порт адаптера.': 'Saved port is unavailable. Select the adapter port.',
'Зв’язок перервано або сканер не відповів. Перевірте кабель і REMOTE, потім підключіться знову.': 'Connection interrupted or no scanner response. Check the cable and REMOTE, then reconnect.',

'Показувати': 'View',
'Періоди активності': 'Activity periods',
'Підсумок за день': 'Daily summary',
'Сортування підсумку': 'Summary sorting',
'За частотою': 'By frequency',
'За кількістю періодів': 'By period count',
'Періодів': 'Periods',
'Рядків підсумку: {count}. Сторінка {page}/{pages}.': 'Summary rows: {count}. Page {page}/{pages}.',
'Періоди — спостереження, не кількість розмов. Один період через північ може враховуватися в обох днях.': 'Periods are observations, not conversation counts. A period spanning midnight may count on both days.',

'Відкрити журнал': 'Open log',
'Історія активності': 'Activity history',
'Дата РРРР-ММ-ДД': 'Date YYYY-MM-DD',
'Застосувати': 'Apply',
'Скинути': 'Reset',
'Виберіть CSV-журнал. Сканер не потрібен.': 'Select a CSV log. No scanner required.',
'Попередня': 'Previous',
'Наступна': 'Next',
'Дата — місцева дата з журналу. Назви — поточні збережені підписи. CSV не змінюється.': 'Date uses the local date recorded in the log. Names are your current saved labels. CSV is unchanged.',
'Читаємо журнал…': 'Reading log…',
'Не вдалося прочитати журнал.': 'Could not read the log.',
'Рядків: {rows}. Періодів: {periods}. Пропущено пошкоджених рядків: {skipped}.': 'Rows: {rows}. Periods: {periods}. Malformed rows skipped: {skipped}.',
'Немає підтверджених записів активності; сирі відповіді не перетворюємо на передачі.': 'No confirmed activity records; raw responses are not inferred as transmissions.',
'Дата': 'Date',
'Введіть дату РРРР-ММ-ДД або залиште поле порожнім.': 'Enter a date as YYYY-MM-DD or leave the field blank.',
'Знайдено періодів: {count}. Сторінка {page}/{pages}.': 'Matching periods: {count}. Page {page}/{pages}.',

'PRO-2052 — Журнал активності': 'PRO-2052 — Activity log',
'Частоти й час спостережень': 'Frequencies and observation times',
'Порт': 'Port', 'Оновити порти': 'Refresh ports', 'Швидкість': 'Baud rate',
'Почати': 'Start', 'Зупинити': 'Stop', 'Опитування': 'Polling',
'Змінюйте режим після зупинки запису.': 'Stop monitoring before changing the polling mode.',
'Дата й час ПК (із часовим зсувом)': 'PC date and time (with UTC offset)',
'Канал': 'Channel', 'Частота, МГц': 'Frequency, MHz',
'Рядок — перевірене спостереження, не окрема розмова чи точний час її початку.':
'A row is a rechecked observation, not a separate conversation or its exact start time.',
'Діагностика — останні відповіді сканера': 'Diagnostics — latest scanner responses',
'Журнали зберігаються у вашій папці даних → logs.': 'CSV files will be saved in data/logs. Use the Data folder button.',
'Готово. Увімкніть REMOTE: SFT має блимати.': 'Ready. Enable REMOTE: SFT should flash.',
'Потрібен pyserial: встановіть залежності з requirements.txt.': 'pyserial is required: install the dependencies in requirements.txt.',
'Виберіть порт сканера зі списку.': 'Select the scanner port from the list.',
'Підключення та перевірка відповіді…': 'Connecting and checking the response…',
'Завершуємо поточну перевірку й закриваємо порт…': 'Finishing the current check and closing the port…',
'Зупинено. Порт закрито; записані дані збережено.': 'Stopped. Port closed; recorded data saved.',
'Опитування зупинено. Перевірте діагностику, REMOTE та швидкість.': 'Polling stopped. Check diagnostics, REMOTE and baud rate.',
'Шумоподавлювач відкритий. Спостерігаємо…': 'Squelch open. Monitoring…',
'Шумоподавлювач закритий. Спостерігаємо…': 'Squelch closed. Monitoring…',
'Отримано SQ. Дивіться діагностику.': 'SQ response received. See diagnostics.',
'Мова': 'Language',
'Назва': 'Name', 'Назва частоти': 'Frequency name',
'Двічі натисніть рядок, щоб назвати частоту.': 'Double-click a row to name its frequency.',
'Введіть назву. Порожнє поле видаляє назву.': 'Enter a name. Leave blank to remove the name.',
'Зберегти': 'Save', 'Скасувати': 'Cancel',
'Назва має бути одним рядком до 120 символів.': 'Use a single line of up to 120 characters.',
'Не вдалося прочитати файл назв. Початковий файл збережено.': 'Could not read the names file. The original file has been preserved.',
'Не вдалося зберегти назву.': 'Could not save the name.',
'Перше виявлення': 'First observed',
'Останнє виявлення': 'Last observed',
'Спостережень': 'Samples',
'Рядок — період спостережень, не гарантовано безперервна розмова. Час ПК із часовим зсувом.':
'A row is an observation period, not necessarily a continuous conversation. PC time includes UTC offset.',
}
REVERSE = {v:k for k,v in TEXT.items()}


def translate(value, language):
    original = REVERSE.get(value, value)
    original = original.replace(' • Latest 1000 periods shown; CSV contains all observations',
                                ' • У таблиці останні 1000 періодів, у CSV — усі спостереження')
    for uk,en in [('Не вдалося прочитати порти: ', 'Could not list ports: '),
                  ('Спостережень: ', 'Observations: ')]:
        if original.startswith(en):
            original = uk + original[len(en):]
        if original.startswith(uk):
            original = original.replace(' • Latest 1000 shown; CSV contains all', ' • У таблиці останні 1000, у CSV — усі')
            if language == 'en':
                return (en + original[len(uk):]).replace(' • У таблиці останні 1000 періодів, у CSV — усі спостереження', ' • Latest 1000 periods shown; CSV contains all observations').replace(' • У таблиці останні 1000, у CSV — усі', ' • Latest 1000 shown; CSV contains all')
            return original
    return TEXT.get(original, original) if language == 'en' else original


class LanguageUI:
    def __init__(self, app, parent, settings_path=None):
        self.app = app
        self.path = Path(settings_path) if settings_path else Path(__file__).with_name('ui-settings.json')
        self.language = 'uk'
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if saved.get('language') in ('uk', 'en'):
                self.language = saved['language']
        except (OSError, ValueError, AttributeError):
            pass
        self.choice = tk.StringVar(value='English' if self.language=='en' else 'Українська')
        row = ttk.Frame(parent)
        row.pack(side='right')
        ttk.Label(row, text='Мова').pack(side='left', padx=6)
        self.combo = ttk.Combobox(row, textvariable=self.choice, values=['Українська','English'], state='readonly', width=11)
        self.combo.pack(side='left')
        self.combo.bind('<<ComboboxSelected>>', self.changed)
        self.widgets = []
        self.collect(app.root)
        self.original_title = app.root.title()
        self.headings = {key:app.tree.heading(key)['text'] for key in app.tree['columns']}
        self.variables = [app.status, app.summary, app.log_path]
        for variable in self.variables:
            variable.trace_add('write', lambda *args, var=variable: self.variable_changed(var))
        self.apply()

    def collect(self, widget):
        if 'text' in widget.keys() and not widget.cget('textvariable'):
            value = widget.cget('text')
            if value in TEXT:
                self.widgets.append((widget,value))
        for child in widget.winfo_children():
            self.collect(child)

    def variable_changed(self, variable):
        value = translate(variable.get(), self.language)
        if value != variable.get():
            variable.set(value)

    def apply(self):
        if hasattr(self.app, 'remote'):
            self.app.remote.retranslate()
        if hasattr(self.app, 'search'):
            self.app.search.retranslate()
        if hasattr(self.app, 'notebook'):
            self.app.notebook.tab(0, text='Monitoring' if self.language=='en' else 'Моніторинг')
        if hasattr(self.app, 'programming'):
            self.app.programming.retranslate()
        for widget,value in self.widgets:
            widget.configure(text=translate(value,self.language))
        self.app.root.title(translate(self.original_title,self.language))
        for key,value in self.headings.items():
            self.app.tree.heading(key,text=translate(value,self.language))
        fast = self.app.pace.get() in ('Швидше','Faster')
        labels = ['Normal','Faster'] if self.language=='en' else ['Звичайне','Швидше']
        self.app.paces['values'] = labels
        self.app.pace.set(labels[int(fast)])
        for variable in self.variables:
            self.variable_changed(variable)

    def changed(self, event=None):
        self.language = 'en' if self.choice.get()=='English' else 'uk'
        self.apply()
        try:
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps({'language':self.language}), encoding='utf-8')
            temp.replace(self.path)
        except OSError as exc:
            messagebox.showwarning('Language / Мова', 'Could not save language / Не вдалося зберегти мову:\n'+str(exc))

    def text(self, value):
        return translate(value,self.language)
