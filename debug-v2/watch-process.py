"""Retain an authoritative process handle and log exit without touching windows."""
import ctypes,json,sys,time
from ctypes import wintypes as W
from harness import identify,ROOT
pid=int(sys.argv[1]);assert identify()==pid
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
k.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];k.GetExitCodeProcess.restype=W.BOOL
k.CloseHandle.argtypes=[W.HANDLE]
h=k.OpenProcess(0x101000,False,pid)
if not h:raise ctypes.WinError(ctypes.get_last_error())
try:
    while k.WaitForSingleObject(h,1000)==258:pass
    code=W.DWORD()
    if not k.GetExitCodeProcess(h,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
    (ROOT/f'diagnostics-v2/game-exit-{pid}.json').write_text(json.dumps({'pid':pid,'exitCode':hex(code.value),'time':time.time()},indent=2),encoding='utf-8')
finally:k.CloseHandle(h)
