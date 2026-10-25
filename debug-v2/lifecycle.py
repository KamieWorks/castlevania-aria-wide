"""Close only the verified game window, optionally deploy the test proxy and launch via Steam."""
from debug_config import debug_root
import argparse,ctypes,pathlib,os,time,shutil,hashlib,subprocess,sys
from ctypes import wintypes as W
from harness import identify,EXE,ROOT
p=argparse.ArgumentParser();p.add_argument('action',choices=['close','launch','deploy']);p.add_argument('--dll',default='d3d9-v2-test.dll');p.add_argument('--replace-test',action='store_true');a=p.parse_args()
if a.action in ('close','deploy'):
    pid=identify();user=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback,W.LPARAM];user.EnumWindows.restype=W.BOOL
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)];user.GetWindowThreadProcessId.restype=W.DWORD
    user.IsWindowVisible.argtypes=[W.HWND];user.IsWindowVisible.restype=W.BOOL
    user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.PostMessageW.restype=W.BOOL
    windows=[]
    @callback
    def visit(hwnd,param):
        owner=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):windows.append(hwnd)
        return True
    user.EnumWindows(visit,0)
    if len(windows)!=1:raise RuntimeError(f'Ambiguous visible game window: {windows}')
    if not user.PostMessageW(windows[0],0x10,0,0):raise ctypes.WinError(ctypes.get_last_error())
    for _ in range(100):
        time.sleep(.1)
        try:identify()
        except RuntimeError as e:
            if 'found []' in str(e):break
            raise
    else:raise RuntimeError('Game did not close gracefully')
    print({'closedPid':pid})
if a.action=='deploy':
    destination=EXE.parent/'d3d9.dll'
    if destination.exists():
        if not a.replace_test:raise RuntimeError('Active DLL already exists; preserve it explicitly before replacing')
        # Only replace a byte-identical binary from our own test output directory.
        digest=hashlib.sha256(destination.read_bytes()).hexdigest()
        temp=debug_root()
        known=any(hashlib.sha256(f.read_bytes()).hexdigest()==digest for f in temp.glob('d3d9-v*-test.dll'))
        if not known:raise RuntimeError('Unrecognized active DLL; refusing replacement')
        backup=ROOT/'private-v2/test-dll-backups';backup.mkdir(exist_ok=True)
        os.replace(destination,backup/f'd3d9-{digest[:12]}-{time.time_ns()}.dll')
    if pathlib.Path(a.dll).name!=a.dll:raise ValueError('Use a test DLL filename')
    source=debug_root()/a.dll
    shutil.copy2(source,destination);print({'deployed':str(destination)})
if a.action in ('launch','deploy'):
    subprocess.run([sys.executable,str(ROOT/'debug-v2/quiet-game.py'),'--launch','--seconds','8'],check=True,timeout=25)
