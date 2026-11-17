from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import hashlib, json, shutil, subprocess
ROOT=Path(__file__).resolve().parent.parent
msi=C.WinDLL('msi'); H=W.UINT
def api(name,args,restype=W.UINT):
    f=getattr(msi,name);f.argtypes=args;f.restype=restype;return f
op=api('MsiOpenDatabaseW',[W.LPCWSTR,C.c_void_p,C.POINTER(H)])
ov=api('MsiDatabaseOpenViewW',[H,W.LPCWSTR,C.POINTER(H)])
ex=api('MsiViewExecute',[H,H]);fetch=api('MsiViewFetch',[H,C.POINTER(H)])
gs=api('MsiRecordGetStringW',[H,W.UINT,W.LPWSTR,C.POINTER(W.DWORD)])
rs=api('MsiRecordReadStream',[H,W.UINT,C.c_void_p,C.POINTER(W.DWORD)])
close=api('MsiCloseHandle',[H])
def check(code):
    if code: raise RuntimeError(code)
db=H();check(op(str(ROOT/'dist/windows/PRO2052-1.0.0-Setup.msi'),None,C.byref(db)))
def query(statement,stream_path=None):
    v=H();check(ov(db,statement,C.byref(v)));check(ex(v,0));rows=[]
    while True:
        r=H();code=fetch(v,C.byref(r))
        if code==259:break
        check(code)
        if stream_path:
            with stream_path.open('wb') as f:
                while True:
                    buf=C.create_string_buffer(65536);n=W.DWORD(65536);check(rs(r,1,buf,C.byref(n)))
                    if not n.value:break
                    f.write(buf.raw[:n.value])
        else:
            count=msi.MsiRecordGetFieldCount(r);row=[]
            for i in range(1,count+1):
                buf=C.create_unicode_buffer(8192);n=W.DWORD(8192);check(gs(r,i,buf,C.byref(n)));row.append(buf.value)
            rows.append(row)
        close(r)
    close(v);return rows
props=dict(query('SELECT `Property`, `Value` FROM `Property`'))
assert props['ProductVersion']=='1.0.0' and props['ALLUSERS']=='1'
assert props['LIMITUI']=='1' and props['ARPNOMODIFY']=='1'
dirs={r[0]:r[1:] for r in query('SELECT * FROM `Directory`')}
assert dirs['INSTALLDIR']==['ProgramFiles64Folder','PRO2052']
for did,(parent,name) in dirs.items():
    assert not parent or parent in dirs
files={r[0]:r[1:] for r in query('SELECT * FROM `File`')}
comps={r[0]:r[1:] for r in query('SELECT * FROM `Component`')}
features=query('SELECT * FROM `FeatureComponents`')
assert set(comps)=={r[1] for r in features}
for fid,row in files.items():
    cid=row[0];assert cid in comps and comps[cid][1] in dirs and comps[cid][4]==fid
    assert len(row[1].split('|')[0].split('.')[0])<=8
shortcuts=query('SELECT * FROM `Shortcut`');assert len(shortcuts)==2
assert {r[1] for r in shortcuts}=={'AppMenuFolder','DesktopFolder'}
assert len(query('SELECT * FROM `MsiShortcutProperty`'))==2
upgrades=query('SELECT * FROM `Upgrade`');assert len(upgrades)==2
assert {r[-1] for r in upgrades}=={'OLDERPRODUCTS','NEWERPRODUCTS'}
actions={r[0]:r for r in query('SELECT * FROM `InstallExecuteSequence`')}
assert int(actions['InstallInitialize'][2]) < int(actions['RemoveExistingProducts'][2]) < int(actions['ProcessComponents'][2])
assert not any('AppData' in key for key in dirs)
cab=ROOT/'build/msi/embedded-verified.cab'
query("SELECT `Data` FROM `_Streams` WHERE `Name` = 'payload.cab'",cab)
close(db)
extracted=ROOT/'build/msi/verified-files';extracted.mkdir(exist_ok=True)
with (ROOT/'build/msi/extract-verified.log').open('w') as log:
    subprocess.run(['expand.exe','-F:*',str(cab),str(extracted)],stdout=log,stderr=subprocess.STDOUT,check=True)
manifest=json.loads((ROOT/'build/msi/manifest.json').read_text())
assert len(manifest)==len(files)
payload=ROOT/'build/msi/verified-app';payload.mkdir(exist_ok=True)
for item in manifest:
    p=extracted/item['id'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
    assert Path(item['path']).parts[0] != 'data'
    dest=payload/item['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
report=ROOT/'build/msi/final-self-test.json'
result=subprocess.run([str(payload/'PRO2052.exe'),'--self-test',str(report)],timeout=45)
assert result.returncode==0
app=json.loads(report.read_text(encoding='utf-8'));assert app['ok'] and app['version']=='1.0.0'
summary={'msi':'PRO2052-1.0.0-Setup.msi','sha256':hashlib.sha256((ROOT/'dist/windows/PRO2052-1.0.0-Setup.msi').read_bytes()).hexdigest(),'files_verified':len(manifest),'structure':'passed','packaged_app_self_test':app,'full_install_uninstall':'Not executed: Windows Installer service access unavailable in build environment.'}
(ROOT/'dist/windows/PRO2052-1.0.0-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('Verified MSI structure, shortcuts, upgrade rules and all',len(manifest),'embedded file hashes. Extracted application self-test passed.')
