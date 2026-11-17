from platform_support import default_data_folder, valid_port, normalize_port
"""Versioned app configuration and data storage outside the executable bundle."""
import json
import os
from pathlib import Path
import re
import shutil
import sys

VERSION = '1.0.0'


def app_folder():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def data_folder():
    override = os.environ.get('PRO2052_DATA_DIR')
    if override:
        return Path(override).resolve()
    return default_data_folder()


def prepare_data(target, legacy=None):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    (target / 'logs').mkdir(exist_ok=True)
    if legacy and Path(legacy).resolve() != target.resolve() and not (target / 'migration-v1.json').exists():
        legacy = Path(legacy)
        import_legacy_data(legacy, target)
        atomic_json(target / 'migration-v1.json', {'source': str(legacy), 'version': VERSION})
    return target



def import_legacy_data(source, target):
    """Copy only application data; never replace existing data or follow links."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if (source / 'data').is_dir():
        source = (source / 'data').resolve()
    if source == target:
        raise ValueError('Source and destination are the same folder')
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    candidates = [source / name for name in ('frequency-names.json', 'ui-settings.json', 'connection.json')]
    for folder in ('logs', 'channel-backups', 'channel-inventories', 'search-backups'):
        if (source / folder).is_dir():
            candidates.extend((source / folder).rglob('*'))
    for old in candidates:
        if old.is_symlink() or not old.is_file() or not old.resolve().is_relative_to(source):
            continue
        new = target / old.relative_to(source)
        if not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            with old.open('rb') as src, new.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def atomic_json(path, values):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def load_connection(path):
    defaults = {'port': 'COM5' if sys.platform == 'win32' else '', 'baud': '19200', 'pace': 'normal'}
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict): return defaults
        if valid_port(data.get('port','')):
            defaults['port'] = normalize_port(data['port'])
        if str(data.get('baud')) in ('2400','4800','9600','19200'):
            defaults['baud'] = str(data['baud'])
        if data.get('pace') in ('normal','fast'):
            defaults['pace'] = data['pace']
    except (OSError, ValueError):
        pass
    return defaults
