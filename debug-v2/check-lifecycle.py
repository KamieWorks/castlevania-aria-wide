"""Bounded Steam launch / single visible HWND close, with an actual exit code.

Optionally removes only our known experimental proxy for a vanilla comparison.
The proxy is restored in finally; no ROM or save is modified by this script.
"""
from debug_config import debug_root
import argparse,ctypes,hashlib,json,os,pathlib,time,subprocess,sys
from ctypes import wintypes as W
from harness import identify,EXE,ROOT
p=argparse.ArgumentParser();p.add_argument('--vanilla',action='store_true');p.add_argument('--hold',type=float,default=10);a=p.parse_args()
try:
    identify()
except RuntimeError as e:
    if 'found []' not in str(e):raise
else:raise RuntimeError('An existing game must be closed first')
u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
CB=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
u.EnumWindows.argtypes=[CB,W.LPARAM];u.EnumWindows.restype=W.BOOL
u.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)];u.GetWindowThreadProcessId.restype=W.DWORD
u.IsWindowVisible.argtypes=[W.HWND];u.IsWindowVisible.restype=W.BOOL
u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int]
u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];u.PostMessageW.restype=W.BOOL
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];k.GetExitCodeProcess.restype=W.BOOL
k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
k.CloseHandle.argtypes=[W.HANDLE]
destination=EXE.parent/'d3d9.dll';saved=None;handle=None
report={'vanilla':a.vanilla,'time':time.time(),'hold':a.hold}
try:
    if destination.exists():
        digest=hashlib.sha256(destination.read_bytes()).hexdigest();report['proxySha256']=digest
        temp=debug_root()
        if not any(hashlib.sha256(f.read_bytes()).hexdigest()==digest for f in temp.glob('d3d9-v*-test.dll')):raise RuntimeError('Unrecognized proxy')
        if a.vanilla:
            saved=ROOT/'private-v2/test-dll-backups'/f'lifecycle-{time.time_ns()}.dll'
            saved.parent.mkdir(exist_ok=True);os.replace(destination,saved)
    subprocess.run([sys.executable,str(ROOT/'debug-v2/quiet-game.py'),'--launch','--seconds','8'],check=True,timeout=25);deadline=time.monotonic()+35
    while True:
        try:pid=identify();break
        except RuntimeError as e:
            if 'found []' not in str(e) or time.monotonic()>deadline:raise
            time.sleep(.25)
    report['pid']=pid;handle=k.OpenProcess(0x101000,False,pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(a.hold)
    windows=[]
    @CB
    def visit(hwnd,_):
        owner=W.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:
            title=ctypes.create_unicode_buffer(512);u.GetWindowTextW(hwnd,title,len(title))
            windows.append({'hwnd':hwnd,'visible':bool(u.IsWindowVisible(hwnd)),'title':title.value})
        return True
    u.EnumWindows(visit,0);report['windows']=windows
    main=[w['hwnd'] for w in windows if w['visible']]
    if len(main)!=1:raise RuntimeError(f'Expected one visible game window: {main}')
    if not u.PostMessageW(main[0],0x10,0,0):raise ctypes.WinError(ctypes.get_last_error())
    # Bounded 0.1s polls keep the process handle authoritative during WER cleanup.
    deadline=time.monotonic()+30
    while k.WaitForSingleObject(handle,100)==258:
        if time.monotonic()>deadline:raise RuntimeError('Close did not complete within 30s')
    code=W.DWORD()
    if not k.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
    report['exitCode']=hex(code.value)
finally:
    if handle:k.CloseHandle(handle)
    if saved is not None:
        if destination.exists():raise RuntimeError('Refusing to overwrite a new proxy during restoration')
        os.replace(saved,destination)
    out=ROOT/'diagnostics-v2'/('lifecycle-'+('vanilla' if a.vanilla else 'proxy')+'-'+str(time.time_ns())+'.json')
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
