"""Soft orchid accents with high-contrast controls and quiet floral artwork."""
import math
import tkinter as tk
from tkinter import ttk

BG = '#faf6fc'
INK = '#38283f'
ACCENT = '#83548f'

def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    root.configure(background=BG)
    style.configure('.', font=('Helvetica Neue', 9), background=BG, foreground=INK)
    style.configure('TFrame', background=BG)
    style.configure('TLabel', background=BG, foreground=INK)
    style.configure('TButton', padding=(7, 3), background='#f0e5f3', bordercolor='#d9c7e0', lightcolor='#f0e5f3', darkcolor='#d9c7e0')
    style.map('TButton', background=[('active', '#e6d4ed'), ('pressed', '#dcc4e5')], foreground=[('disabled', '#96889b')])
    style.configure('Accent.TButton', background=ACCENT, foreground='white')
    style.map('Accent.TButton', background=[('disabled', '#e1d7e5'), ('pressed', '#684071'), ('active', '#73467f')], foreground=[('disabled', '#96889b'), ('!disabled', 'white')])
    style.configure('TNotebook', background=BG, borderwidth=0)
    style.configure('TNotebook.Tab', padding=(10, 5), background='#eee4f3')
    style.map('TNotebook.Tab', background=[('selected', '#dfcce8'), ('active', '#e8d9ef')], foreground=[('selected', '#4c285b')])
    style.configure('Treeview', background='white', fieldbackground='white', foreground=INK, rowheight=26, bordercolor='#e3d6e8')
    style.configure('Treeview.Heading', background='#eee4f3', foreground='#54345f', font=('Helvetica Neue', 10, 'bold'), padding=(5, 5))
    style.map('Treeview', background=[('selected', '#80558d')], foreground=[('selected', 'white')])
    style.configure('TEntry', fieldbackground='white', padding=4)
    style.configure('TCombobox', fieldbackground='white', padding=3)
    style.map('TCombobox', fieldbackground=[('readonly', 'white')], selectbackground=[('readonly', 'white')], selectforeground=[('readonly', INK)])
    style.configure('TLabelframe', background=BG, bordercolor='#ddcde4')
    style.configure('TLabelframe.Label', background=BG, foreground='#704c7d', font=('Helvetica Neue', 10, 'bold'))

def make_header(parent, version):
    row = ttk.Frame(parent)
    row.pack(fill='x')
    ttk.Label(row, text=f'RadioShack PRO-2052  •  {version}', font=('Helvetica Neue', 20, 'bold'), foreground='#684172').pack(side='left')
    art = tk.Canvas(row, width=80, height=44, bg=BG, highlightthickness=0)
    art.pack(side='right')
    for cx, cy, radius, color in [(31, 23, 10, '#e9bbd4'), (60, 13, 6, '#d7c1ea')]:
        for i in range(5):
            angle = i * math.tau / 5 - math.pi / 2
            x, y = cx + math.cos(angle)*radius*.7, cy + math.sin(angle)*radius*.7
            art.create_oval(x-radius*.55, y-radius*.55, x+radius*.55, y+radius*.55, fill=color, outline='')
        art.create_oval(cx-3, cy-3, cx+3, cy+3, fill='#ae7f57', outline='')
