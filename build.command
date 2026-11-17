#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec > >(tee build.log) 2>&1
trap 'echo; echo "Збирання зупинено. Надішліть повідомлення помилки з цього вікна."; read -r -p "Enter для закриття…"' ERR
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "x86_64" ]]; then
  echo "Цей комплект призначено для Intel Mac."; exit 1
fi
PYTHON=""
for candidate in python3.13 python3.12; do
  if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
done
if [[ -z "$PYTHON" ]]; then
  echo "Встановіть Python 3.13 для macOS з python.org, потім повторіть запуск."; exit 1
fi
"$PYTHON" -c 'import tkinter; print("Python і Tkinter доступні")'
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install pyserial==3.5 pyinstaller==6.22.3
.venv/bin/python build_mac.py
echo
echo "Готово: dist/PRO2052.app та dist/PRO2052-1.0.0-Intel.dmg"
open dist
read -r -p "Enter для закриття…"
