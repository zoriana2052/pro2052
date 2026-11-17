"""Build a self-contained MSI using Windows' own MSI and cabinet APIs."""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT/'dist/windows/PRO2052'
OUT = ROOT/'dist/windows/PRO2052-1.0.0-Setup.msi'
WORK = ROOT/'build/msi'
WORK.mkdir(parents=True,exist_ok=True)
msi = C.WinDLL('msi')
H = W.UINT
def api(name, args, restype=W.UINT):
    fn=getattr(msi,name); fn.argtypes=args; fn.restype=restype; return fn
open_db=api('MsiOpenDatabaseW',[W.LPCWSTR,C.c_void_p,C.POINTER(H)])
open_view=api('MsiDatabaseOpenViewW',[H,W.LPCWSTR,C.POINTER(H)])
execute=api('MsiViewExecute',[H,H])
close=api('MsiCloseHandle',[H])
record=api('MsiCreateRecord',[W.UINT],H)
setstr=api('MsiRecordSetStringW',[H,W.UINT,W.LPCWSTR])
setint=api('MsiRecordSetInteger',[H,W.UINT,C.c_int])
setstream=api('MsiRecordSetStreamW',[H,W.UINT,W.LPCWSTR])
commit=api('MsiDatabaseCommit',[H])
summary=api('MsiGetSummaryInformationW',[H,W.LPCWSTR,W.UINT,C.POINTER(H)])
sumset=api('MsiSummaryInfoSetPropertyW',[H,W.UINT,W.UINT,C.c_int,C.c_void_p,W.LPCWSTR])
sumpersist=api('MsiSummaryInfoPersist',[H])
fileversion=api('MsiGetFileVersionW',[W.LPCWSTR,W.LPWSTR,C.POINTER(W.DWORD),W.LPWSTR,C.POINTER(W.DWORD)])
filehash=api('MsiGetFileHashW',[W.LPCWSTR,W.DWORD,C.c_void_p])
def check(code):
    if code: raise RuntimeError(f'Windows Installer error {code}')
def guid(label): return '{'+str(uuid.uuid5(uuid.NAMESPACE_URL,'pro2052-desktop/'+label)).upper()+'}'
def ident(prefix, value): return prefix+hashlib.sha256(value.encode()).hexdigest()[:24]
def filename(name):
    if re.fullmatch(r'[A-Za-z0-9_~!-]{1,8}(\.[A-Za-z0-9_~-]{1,3})?', name):
        return name
    suffix=Path(name).suffix[1:4].upper()
    short=hashlib.sha256(name.encode()).hexdigest()[:8].upper()
    if suffix and suffix.isalnum(): short+='.'+suffix
    return short+'|'+name
if OUT.exists(): OUT.unlink()
db=H(); check(open_db(str(OUT),C.c_void_p(3),C.byref(db)))
def sql(query, values=None):
    view=H(); check(open_view(db,query,C.byref(view)))
    rec=record(len(values)) if values else H(0)
    try:
        if values:
            for i,v in enumerate(values,1):
                if v is None: continue
                if isinstance(v,Path): check(setstream(rec,i,str(v)))
                elif isinstance(v,int): check(setint(rec,i,v))
                else: check(setstr(rec,i,str(v)))
        check(execute(view,rec))
    finally:
        if rec: close(rec)
        close(view)
def table(name, columns, keys):
    sql('CREATE TABLE `'+name+'` ('+', '.join('`'+col+'` '+typ for col,typ in columns)+' PRIMARY KEY '+', '.join('`'+key+'`' for key in keys)+')')
def add(name, *values):
    columns=', '.join('`'+col+'`' for col,typ in schemas[name][0])
    sql('INSERT INTO `'+name+'` ('+columns+') VALUES ('+', '.join('?' for _ in values)+')',values)

schemas = {
 'Property': ([('Property','CHAR(72) NOT NULL'),('Value','CHAR(0) NOT NULL')],['Property']),
 'Directory': ([('Directory','CHAR(72) NOT NULL'),('Directory_Parent','CHAR(72)'),('DefaultDir','CHAR(255) NOT NULL')],['Directory']),
 'Component': ([('Component','CHAR(72) NOT NULL'),('ComponentId','CHAR(38)'),('Directory_','CHAR(72) NOT NULL'),('Attributes','SHORT NOT NULL'),('Condition','CHAR(255)'),('KeyPath','CHAR(72)')],['Component']),
 'Feature': ([('Feature','CHAR(38) NOT NULL'),('Feature_Parent','CHAR(38)'),('Title','CHAR(64)'),('Description','CHAR(255)'),('Display','SHORT'),('Level','SHORT NOT NULL'),('Directory_','CHAR(72)'),('Attributes','SHORT NOT NULL')],['Feature']),
 'FeatureComponents': ([('Feature_','CHAR(38) NOT NULL'),('Component_','CHAR(72) NOT NULL')],['Feature_','Component_']),
 'File': ([('File','CHAR(72) NOT NULL'),('Component_','CHAR(72) NOT NULL'),('FileName','CHAR(255) NOT NULL'),('FileSize','LONG NOT NULL'),('Version','CHAR(72)'),('Language','CHAR(20)'),('Attributes','SHORT'),('Sequence','LONG NOT NULL')],['File']),
 'MsiFileHash': ([('File_','CHAR(72) NOT NULL'),('Options','SHORT NOT NULL')]+[(f'HashPart{i}','LONG NOT NULL') for i in range(1,5)],['File_']),
 'Media': ([('DiskId','SHORT NOT NULL'),('LastSequence','LONG NOT NULL'),('DiskPrompt','CHAR(64)'),('Cabinet','CHAR(255)'),('VolumeLabel','CHAR(32)'),('Source','CHAR(72)')],['DiskId']),
 'Icon': ([('Name','CHAR(72) NOT NULL'),('Data','OBJECT NOT NULL')],['Name']),
 'Shortcut': ([('Shortcut','CHAR(72) NOT NULL'),('Directory_','CHAR(72) NOT NULL'),('Name','CHAR(128) NOT NULL'),('Component_','CHAR(72) NOT NULL'),('Target','CHAR(72) NOT NULL'),('Arguments','CHAR(255)'),('Description','CHAR(255)'),('Hotkey','SHORT'),('Icon_','CHAR(72)'),('IconIndex','SHORT'),('ShowCmd','SHORT'),('WkDir','CHAR(72)')],['Shortcut']),
 'MsiShortcutProperty': ([('MsiShortcutProperty','CHAR(72) NOT NULL'),('Shortcut_','CHAR(72) NOT NULL'),('PropertyKey','CHAR(255) NOT NULL'),('PropVariantValue','CHAR(0) NOT NULL')],['MsiShortcutProperty']),
 'Upgrade': ([('UpgradeCode','CHAR(38) NOT NULL'),('VersionMin','CHAR(20)'),('VersionMax','CHAR(20)'),('Language','CHAR(255)'),('Attributes','SHORT NOT NULL'),('Remove','CHAR(255)'),('ActionProperty','CHAR(72) NOT NULL')],['UpgradeCode','VersionMin','VersionMax','Language','Attributes']),
 'LaunchCondition': ([('Condition','CHAR(255) NOT NULL'),('Description','CHAR(255) NOT NULL')],['Condition']),
 'RemoveFile': ([('FileKey','CHAR(72) NOT NULL'),('Component_','CHAR(72) NOT NULL'),('FileName','CHAR(255)'),('DirProperty','CHAR(72) NOT NULL'),('InstallMode','SHORT NOT NULL')],['FileKey']),
}
for name in ('InstallExecuteSequence','InstallUISequence','AdminExecuteSequence','AdminUISequence'):
    schemas[name]=([('Action','CHAR(72) NOT NULL'),('Condition','CHAR(255)'),('Sequence','SHORT')],['Action'])
for name,(cols,keys) in schemas.items(): table(name,cols,keys)
properties={
 'ProductCode':guid('product/1.0.0'), 'UpgradeCode':guid('upgrade'), 'ProductName':'PRO2052', 'ProductVersion':'1.0.0',
 'ProductLanguage':'1033', 'Manufacturer':'pro2052', 'ALLUSERS':'1', 'INSTALLLEVEL':'1',
 'LIMITUI':'1','ARPNOMODIFY':'1','ARPPRODUCTICON':'scanner.ico','ARPHELPLINK':'',
 'SecureCustomProperties':'OLDERPRODUCTS;NEWERPRODUCTS;INSTALLDIR','MSIRESTARTMANAGERCONTROL':'Disable',
 'ARPCOMMENTS':'RadioShack PRO-2052 desktop companion. User data is preserved during upgrades and uninstall.',
}
for k,v in properties.items():
    if v: add('Property',k,v)
add('Directory','TARGETDIR',None,'SourceDir')
add('Directory','ProgramFiles64Folder','TARGETDIR','.')
add('Directory','INSTALLDIR','ProgramFiles64Folder','PRO2052')
add('Directory','ProgramMenuFolder','TARGETDIR','.')
add('Directory','AppMenuFolder','ProgramMenuFolder','PRO2052')
add('Directory','DesktopFolder','TARGETDIR','.')
directories={Path('.'):'INSTALLDIR'}
for p in sorted([p for p in PAYLOAD.rglob('*') if p.is_dir()], key=lambda p:(len(p.parts),str(p))):
    rel=p.relative_to(PAYLOAD); did=ident('D',rel.as_posix()); directories[rel]=did
    add('Directory',did,directories[rel.parent],filename(p.name))
add('Feature','Main',None,'PRO2052','Desktop application and shortcuts',1,1,'INSTALLDIR',0)
files=sorted(p for p in PAYLOAD.rglob('*') if p.is_file())
manifest=[]; cablines=[]; main_component=None; main_file=None
for seq,p in enumerate(files,1):
    rel=p.relative_to(PAYLOAD); key=rel.as_posix(); fid=ident('F',key); cid=ident('C',key)
    add('Component',cid,guid('component/'+key),directories[rel.parent],256,None,fid)
    add('FeatureComponents','Main',cid)
    ver=C.create_unicode_buffer(256); lang=C.create_unicode_buffer(256); nv=W.DWORD(256); nl=W.DWORD(256)
    status=fileversion(str(p),ver,C.byref(nv),lang,C.byref(nl))
    add('File',fid,cid,filename(p.name),p.stat().st_size,ver.value if status==0 else None,lang.value if status==0 and lang.value else None,512,seq)
    if status:
        h=(W.DWORD*5)(20,0,0,0,0);check(filehash(str(p),0,C.byref(h)))
        add('MsiFileHash',fid,0,*[C.c_int(h[i]).value for i in range(1,5)])
    cablines.append(f'"{p}" {fid}')
    manifest.append({'path':key,'id':fid,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    if key=='PRO2052.exe': main_component=cid; main_file=fid
add('Icon','scanner.ico',ROOT/'packaging/scanner.ico')
for name,directory in [('StartMenuShortcut','AppMenuFolder'),('DesktopShortcut','DesktopFolder')]:
    add('Shortcut',name,directory,'PRO2052',main_component,'[#'+main_file+']',None,'PRO2052 1.0.0',None,'scanner.ico',0,1,'INSTALLDIR')
    add('MsiShortcutProperty',name+'AppId',name,'System.AppUserModel.ID','PRO2052.Desktop.Scanner')
add('RemoveFile','RemoveAppMenu',main_component,None,'AppMenuFolder',2)
add('Upgrade',guid('upgrade'),None,'1.0.0',None,1,None,'OLDERPRODUCTS')
add('Upgrade',guid('upgrade'),'1.0.0',None,None,2,None,'NEWERPRODUCTS')
add('LaunchCondition','Installed OR (VersionNT64 >= 603)','PRO2052 requires a supported 64-bit Windows version.')
add('LaunchCondition','Installed OR NOT NEWERPRODUCTS','A newer PRO2052 version is already installed.')
actions=[('FindRelatedProducts',None,25),('LaunchConditions',None,100),('ValidateProductID',None,700),('CostInitialize',None,800),('FileCost',None,900),('CostFinalize',None,1000),('MigrateFeatureStates',None,1200),('InstallValidate',None,1400),('InstallInitialize',None,1500),('RemoveExistingProducts','OLDERPRODUCTS',1550),('ProcessComponents',None,1600),('UnpublishFeatures',None,1800),('RemoveShortcuts',None,3200),('RemoveFiles',None,3500),('RemoveFolders',None,3600),('CreateFolders',None,3700),('InstallFiles',None,4000),('CreateShortcuts',None,4500),('RegisterUser',None,6000),('RegisterProduct',None,6100),('PublishFeatures',None,6300),('PublishProduct',None,6400),('InstallFinalize',None,6600)]
for row in actions: add('InstallExecuteSequence',*row)
for row in actions[:7]: add('InstallUISequence',*row)
add('InstallUISequence','ExecuteAction',None,1300)
for row in [('CostInitialize',None,800),('FileCost',None,900),('CostFinalize',None,1000),('InstallValidate',None,1400),('InstallInitialize',None,1500),('InstallAdminPackage',None,3900),('InstallFiles',None,4000),('InstallFinalize',None,6600)]: add('AdminExecuteSequence',*row)
for row in [('CostInitialize',None,800),('FileCost',None,900),('CostFinalize',None,1000),('ExecuteAction',None,1300)]: add('AdminUISequence',*row)
ddf=WORK/'payload.ddf'
ddf.write_text('\n'.join(['.OPTION EXPLICIT','.Set CabinetNameTemplate=payload.cab',f'.Set DiskDirectoryTemplate="{WORK}"','.Set CompressionType=LZX','.Set CompressionMemory=21','.Set Cabinet=ON','.Set Compress=ON','.Set MaxDiskSize=0','.Set MaxCabinetSize=0','.Set MaxDiskFileCount=0','.Set FolderFileCountThreshold=0','.Set FolderSizeThreshold=0']+cablines),encoding='utf-8')
with (WORK/'makecab.log').open('w') as log: subprocess.run(['makecab.exe','/F',str(ddf)],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=WORK)
add('Media',1,len(files),None,'#payload.cab',None,None)
sql('INSERT INTO `_Streams` (`Name`, `Data`) VALUES (?, ?)',('payload.cab',WORK/'payload.cab'))
info=H();check(summary(db,None,20,C.byref(info)))
for prop,typ,val in [(1,2,1252),(2,30,'Installation Database'),(3,30,'PRO2052 1.0.0'),(4,30,'pro2052'),(7,30,'x64;1033'),(9,30,'{'+str(uuid.uuid4()).upper()+'}'),(14,3,500),(15,3,2),(18,30,'PRO2052 native MSI builder')]:
    check(sumset(info,prop,typ,val if isinstance(val,int) else 0,None,val if isinstance(val,str) else None))
check(sumpersist(info));close(info);check(commit(db));close(db)
(WORK/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(f'Created {OUT.name}: {len(files)} files, {OUT.stat().st_size:,} bytes')
