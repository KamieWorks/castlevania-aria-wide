"""Restore game-only mute after exit while retaining its audio interfaces.

No game stream can be audible: interfaces are unmuted only after the verified
debug process has exited. Other apps and endpoint volumes are untouched.
"""
import argparse,ctypes,importlib.util,json,subprocess,sys
from ctypes import wintypes as W
from harness import ROOT,identify
spec=importlib.util.spec_from_file_location('quiet_audio',ROOT/'debug-v2/quiet-game.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
parser=argparse.ArgumentParser();parser.add_argument('--terminate-stuck',action='store_true',help='After a failed normal close, terminate this verified diagnostic process only');args=parser.parse_args()
pid=identify();launch=json.loads((ROOT/'diagnostics-v2/quiet-game-check.json').read_text());assert launch['backgroundGuard'] and launch['launcher']['pid']==pid,launch
ole=ctypes.OleDLL('ole32');ole.CoInitialize(None);held=[];enumerator=q.P();collection=q.P();report={'pid':pid,'sessions':[]}
try:
    clsid=q.GUID('bcde0395-e52f-467c-8e3d-c4579291692e');iid=q.GUID('a95664d2-9614-4f35-a746-de8db63617e6')
    ole.CoCreateInstance.argtypes=[ctypes.POINTER(q.GUID),q.P,W.DWORD,ctypes.POINTER(q.GUID),ctypes.POINTER(q.P)]
    hr=ole.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid),ctypes.byref(enumerator));assert hr>=0,hr
    q.call(enumerator,3,[ctypes.c_int,W.DWORD,ctypes.POINTER(q.P)],0,1,ctypes.byref(collection));count=W.UINT();q.call(collection,3,[ctypes.POINTER(W.UINT)],ctypes.byref(count))
    for i in range(count.value):
        device=q.P();manager=q.P();sessions=q.P()
        try:
            q.call(collection,4,[W.UINT,ctypes.POINTER(q.P)],i,ctypes.byref(device));iid=q.GUID('77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f');q.call(device,3,[ctypes.POINTER(q.GUID),W.DWORD,q.P,ctypes.POINTER(q.P)],ctypes.byref(iid),23,None,ctypes.byref(manager));q.call(manager,5,[ctypes.POINTER(q.P)],ctypes.byref(sessions))
            n=ctypes.c_int();q.call(sessions,3,[ctypes.POINTER(ctypes.c_int)],ctypes.byref(n))
            for j in range(n.value):
                session=q.P();control=q.P()
                try:
                    q.call(sessions,4,[ctypes.c_int,ctypes.POINTER(q.P)],j,ctypes.byref(session));control=q.query(session,'bfb7ff88-7239-4fc9-8fa2-07c950be9c6d');owner=W.DWORD();q.call(control,14,[ctypes.POINTER(W.DWORD)],ctypes.byref(owner))
                    if owner.value==pid:
                        volume=q.query(session,'87ce5498-68d6-44e5-9215-6da47ef883d8');held.append(volume);muted=W.BOOL();q.call(volume,6,[ctypes.POINTER(W.BOOL)],ctypes.byref(muted));assert muted.value,'Debug stream must stay muted until exit'
                        report['sessions'].append({'endpoint':i,'session':j,'before':True})
                finally:q.release(control);q.release(session)
        finally:q.release(sessions);q.release(manager);q.release(device)
    assert held,'No game audio interface retained'
    try:close_failed=subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],timeout=20).returncode!=0
    except subprocess.TimeoutExpired:
        if not args.terminate_stuck:raise
        close_failed=True
    if close_failed:
        if not args.terminate_stuck:raise RuntimeError('Normal close failed; game remains muted')
        assert identify()==pid,'Diagnostic process identity changed'
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
        kernel.TerminateProcess.argtypes=[W.HANDLE,W.UINT];kernel.TerminateProcess.restype=W.BOOL;kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.CloseHandle.argtypes=[W.HANDLE]
        handle=kernel.OpenProcess(0x100001,False,pid);assert handle,ctypes.get_last_error()
        try:
            assert kernel.TerminateProcess(handle,0xe0000001),ctypes.get_last_error();assert kernel.WaitForSingleObject(handle,5000)==0
        finally:kernel.CloseHandle(handle)
        report['forcedDiagnosticExit']={'reason':'Normal close timed out during instrumentation diagnosis','exitCode':'0xe0000001'}
    try:identify()
    except RuntimeError as e:assert 'found []' in str(e),str(e)
    else:raise RuntimeError('Refusing to unmute a running debug game')
    for volume,row in zip(held,report['sessions']):
        q.call(volume,5,[W.BOOL,q.P],False,None);muted=W.BOOL();q.call(volume,6,[ctypes.POINTER(W.BOOL)],ctypes.byref(muted));assert not muted.value;row['after']=False
    report.update(restoredStoppedGameSessions=len(held),gameWasRunningDuringUnmute=False,otherApplicationsChanged=False)
finally:
    for volume in held:q.release(volume)
    q.release(collection);q.release(enumerator);ole.CoUninitialize()
    (ROOT/'diagnostics-v2/audio-restoration-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
