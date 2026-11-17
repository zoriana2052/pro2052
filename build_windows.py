"""Build Windows x64 EXE, portable ZIP and MSI from the shared source."""
from pathlib import Path
import json
import os
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
if sys.platform!='win32' or struct.calcsize('P')!=8:
    raise SystemExit('Use 64-bit Python on Windows.')
os.chdir(ROOT)
def run(*args, **kwargs):
    subprocess.run([str(a) for a in args],check=True,**kwargs)
build=ROOT/'build/windows';build.mkdir(parents=True,exist_ok=True)
dist=ROOT/'dist/windows';dist.mkdir(parents=True,exist_ok=True)
tests=subprocess.run([sys.executable,str(ROOT/'run_tests.py')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(build/'tests.log').write_text(tests.stdout,encoding='utf-8')
print(tests.stdout,flush=True);tests.check_returncode()
run(sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--name','PRO2052',
    '--icon',ROOT/'packaging/scanner.ico','--version-file',ROOT/'packaging/windows-version.txt',
    '--add-data',str(ROOT/'src/scanner.png')+os.pathsep+'.',
    '--distpath',dist,'--workpath',build/'pyinstaller','--specpath',build,ROOT/'src/launcher.py')
payload=dist/'PRO2052'
shutil.copytree(ROOT/'licenses',payload/'licenses',dirs_exist_ok=True)
for name in ('README.md','README-UK.txt'):
    shutil.copy2(ROOT/name,payload/name)
shutil.copy2(ROOT/'src/sample-import.csv',payload/'sample-import.csv')
report=build/'self-test.json'
run(payload/'PRO2052.exe','--self-test',report,timeout=90)
if not json.loads(report.read_text(encoding='utf-8')).get('ok'):
    raise SystemExit('Packaged application self-test failed')
shutil.make_archive(str(dist/'PRO2052-1.0.0-Windows-x64'),'zip',dist,'PRO2052')
run(sys.executable,ROOT/'packaging/build_msi.py')
run(sys.executable,ROOT/'packaging/verify_msi.py')
print('Windows build complete: '+str(dist))
