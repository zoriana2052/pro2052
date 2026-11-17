"""Run on an Intel Mac with Python and PyInstaller installed in the venv."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.platform!='darwin' or platform.machine()!='x86_64':
    raise SystemExit('An Intel Mac is required.')
def run(*args,**kw):
    subprocess.run([str(a) for a in args],check=True,**kw)
build=ROOT/'build';build.mkdir(exist_ok=True)
icons=build/'scanner.iconset';icons.mkdir(exist_ok=True)
source=ROOT/'icon-source.png'
for size in (16,32,128,256,512):
    for scale in (1,2):
        pixels=size*scale
        name=f'icon_{size}x{size}'+('@2x' if scale==2 else '')+'.png'
        run('sips','-z',pixels,pixels,source,'--out',icons/name,stdout=subprocess.DEVNULL)
run('iconutil','-c','icns',icons,'-o',build/'scanner.icns')
tests=subprocess.run([sys.executable,str(ROOT/'run_tests.py'),'test_macos','test_programming','test_periods'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(build/'tests.log').write_text(tests.stdout,encoding='utf-8')
print(tests.stdout,flush=True)
tests.check_returncode()
spec=ROOT/'PRO2052-mac.spec'
spec.write_text('''
from pathlib import Path
root=Path(SPECPATH)
a=Analysis([str(root/'src/launcher.py')],pathex=[str(root/'src')],binaries=[],datas=[(str(root/'src/scanner.png'),'.'),(str(root/'licenses'),'licenses')],hiddenimports=[],hookspath=[],runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='PRO2052',debug=False,strip=False,upx=False,console=False,target_arch='x86_64')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='PRO2052')
app=BUNDLE(coll,name='PRO2052.app',icon=str(root/'build/scanner.icns'),bundle_identifier='local.pro2052.desktop',version='1.0.0',info_plist={'CFBundleShortVersionString':'1.0.0','CFBundleVersion':'1.0.0','NSHighResolutionCapable':True,'NSHumanReadableCopyright':'PRO2052 — pro2052'})
''',encoding='utf-8')
run(sys.executable,'-m','PyInstaller','--noconfirm',spec)
app=ROOT/'dist/PRO2052.app'
run('codesign','--verify','--deep','--strict',app)
binary=app/'Contents/MacOS/PRO2052'
run('lipo','-verify_arch','x86_64',binary)
report=build/'self-test.json'
run(binary,'--self-test',report,timeout=90)
result=json.loads(report.read_text())
if not result.get('ok'):raise SystemExit('Application self-test failed. See build/self-test.json')
# Each run gets a fresh staging folder; previous disk images remain available.
stage=build/('dmg-'+str(time.time_ns()));stage.mkdir()
shutil.copytree(app,stage/'PRO2052.app',symlinks=True)
(stage/'Applications').symlink_to('/Applications')
shutil.copy2(ROOT/'README-UK.txt',stage/'README-UK.txt')
run('hdiutil','create','-volname','PRO2052 1.0.0','-srcfolder',stage,'-ov','-format','UDZO',ROOT/'dist/PRO2052-1.0.0-Intel.dmg')
run('hdiutil','verify',ROOT/'dist/PRO2052-1.0.0-Intel.dmg')
print('Built and self-tested PRO2052 1.0.0 for Intel macOS. No scanner commands were sent.')
