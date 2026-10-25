from debug_config import debug_root
"""Mute only verified game audio sessions; optionally guard a background launch.

Uses Windows Core Audio directly. Never changes endpoint/system volume.
"""
import argparse,ctypes,hashlib,json,os,pathlib,subprocess,time,uuid,sys
from ctypes import wintypes as W
from harness import identify,EXE,ROOT

class GUID(ctypes.Structure):
    _fields_=[('data',ctypes.c_ubyte*16)]
    def __init__(self,value):super().__init__((ctypes.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le))

P=ctypes.c_void_p;H=ctypes.c_long
def call(obj,index,argtypes,*args):
    table=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(P))).contents
    result=ctypes.WINFUNCTYPE(H,P,*argtypes)(table[index])(obj,*args)
    if result<0:raise OSError(f'COM slot {index}: {result & 0xffffffff:08x}')
def release(obj):
    if obj:call(obj,2,[])
def query(obj,iid):
    result=P();g=GUID(iid);call(obj,0,[ctypes.POINTER(GUID),ctypes.POINTER(P)],ctypes.byref(g),ctypes.byref(result));return result

def mute_sessions(pid,muted=True,identifiers=None):
    ole=ctypes.OleDLL('ole32');ole.CoInitialize(None)
    enumerator=P();collection=P();changed=[]
    try:
        clsid=GUID('bcde0395-e52f-467c-8e3d-c4579291692e');iid=GUID('a95664d2-9614-4f35-a746-de8db63617e6')
        ole.CoCreateInstance.argtypes=[ctypes.POINTER(GUID),P,W.DWORD,ctypes.POINTER(GUID),ctypes.POINTER(P)]
        hr=ole.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid),ctypes.byref(enumerator))
        if hr<0:raise OSError(hex(hr & 0xffffffff))
        call(enumerator,3,[ctypes.c_int,W.DWORD,ctypes.POINTER(P)],0,1,ctypes.byref(collection))
        count=W.UINT();call(collection,3,[ctypes.POINTER(W.UINT)],ctypes.byref(count))
        for i in range(count.value):
            device=P();manager=P();sessions=P()
            try:
                call(collection,4,[W.UINT,ctypes.POINTER(P)],i,ctypes.byref(device))
                iid=GUID('77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f')
                call(device,3,[ctypes.POINTER(GUID),W.DWORD,P,ctypes.POINTER(P)],ctypes.byref(iid),23,None,ctypes.byref(manager))
                call(manager,5,[ctypes.POINTER(P)],ctypes.byref(sessions))
                n=ctypes.c_int();call(sessions,3,[ctypes.POINTER(ctypes.c_int)],ctypes.byref(n))
                for j in range(n.value):
                    session=P();control=P();volume=P()
                    try:
                        call(sessions,4,[ctypes.c_int,ctypes.POINTER(P)],j,ctypes.byref(session))
                        control=query(session,'bfb7ff88-7239-4fc9-8fa2-07c950be9c6d')
                        owner=W.DWORD();call(control,14,[ctypes.POINTER(W.DWORD)],ctypes.byref(owner))
                        identifier=P();call(control,12,[ctypes.POINTER(P)],ctypes.byref(identifier))
                        try:session_id=ctypes.wstring_at(identifier)
                        finally:
                            ole.CoTaskMemFree.argtypes=[P];ole.CoTaskMemFree(identifier)
                        selected=session_id in identifiers if identifiers is not None else owner.value==pid
                        if not selected:continue
                        volume=query(session,'87ce5498-68d6-44e5-9215-6da47ef883d8')
                        call(volume,5,[W.BOOL,P],muted,None)
                        observed=W.BOOL();call(volume,6,[ctypes.POINTER(W.BOOL)],ctypes.byref(observed))
                        if bool(observed.value)!=muted:raise RuntimeError('Game session mute state did not change')
                        changed.append({'endpoint':i,'session':j,'muted':muted,'identifier':session_id})
                    finally:release(volume);release(control);release(session)
            finally:release(sessions);release(manager);release(device)
        return changed
    finally:release(collection);release(enumerator);ole.CoUninitialize()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--launch',action='store_true');parser.add_argument('--seconds',type=float,default=5);parser.add_argument('--restore-stopped-audio',action='store_true');args=parser.parse_args()
    keys_path=ROOT/'diagnostics-v2/quiet-audio-identifiers.json'
    if args.restore_stopped_audio:
        assert not args.launch
        try:identify()
        except RuntimeError as e:
            if 'found []' not in str(e):raise
        else:raise RuntimeError('Audio restoration requires the debug game to have exited')
        identifiers=json.loads(keys_path.read_text());changed=mute_sessions(None,False,identifiers)
        report={'restoredStoppedGameSessions':len(changed),'otherApplicationsChanged':False,'gameWasRunning':False}
        (ROOT/'diagnostics-v2/audio-restoration-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));return
    user=ctypes.WinDLL('user32');user.GetForegroundWindow.restype=W.HWND
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    before=user.GetForegroundWindow();game_foreground=False
    ready=None
    if args.launch:
        try:identify()
        except RuntimeError as e:
            if 'found []' not in str(e):raise
        else:raise RuntimeError('Game already running')
        native_guard=debug_root()/'debug-input-v1.dll'
        if not native_guard.exists():
            subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'debug-v2/build-input-guard.ps1')],check=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        launcher=subprocess.Popen(['node',str(ROOT/'debug-v2/background-launch.mjs'),str(EXE),str(EXE.parent)],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/background-launch-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        ready=json.loads(launcher.stdout.readline())
        if not ready.get('backgroundGuard'):raise RuntimeError('Background launch guard failed')
        subprocess.Popen([sys.executable,str(ROOT/'debug-v2/watch-process.py'),str(ready['pid'])],stdout=subprocess.DEVNULL,stderr=open(ROOT/'diagnostics-v2/process-watch-errors.log','a'),creationflags=subprocess.CREATE_NO_WINDOW)
    end=time.monotonic()+args.seconds;seen={};pid=None
    while time.monotonic()<end:
        try:pid=identify()
        except RuntimeError as e:
            if 'found []' not in str(e):raise
            time.sleep(.1);continue
        for session in mute_sessions(pid):seen[(session['endpoint'],session['session'])]=session
        owner=W.DWORD();user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(owner))
        game_foreground=game_foreground or owner.value==pid
        time.sleep(.1)
    keys_path.write_text(json.dumps(sorted({s['identifier'] for s in seen.values()})),encoding='utf-8')
    report={'pid':pid,'launcher':ready,'audioSessions':[{k:v for k,v in s.items() if k!='identifier'} for s in seen.values()],'backgroundGuard':args.launch,'systemVolumeChanged':False,'foregroundBefore':before,'foregroundAfter':user.GetForegroundWindow(),'gameForegroundObserved':game_foreground}
    if args.launch:report.update(nativeInputGuardSha256=hashlib.sha256(native_guard.read_bytes()).hexdigest(),backgroundLauncherSha256=hashlib.sha256((ROOT/'debug-v2/background-launch.mjs').read_bytes()).hexdigest())
    (ROOT/'diagnostics-v2/quiet-game-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':main()
