"""Close the sole verified main HWND through the Windows system Close command."""
import ctypes,json,time,runpy
from ctypes import wintypes as W
from harness import ROOT
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'));u=ctypes.WinDLL('user32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];u.PostMessageW.restype=W.BOOL
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
k.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];k.GetExitCodeProcess.restype=W.BOOL;k.CloseHandle.argtypes=[W.HANDLE]
h=k.OpenProcess(0x101000,False,state['pid']);report={'pid':state['pid'],'method':'WM_SYSCOMMAND/SC_CLOSE','time':time.time()}
if not h:raise ctypes.WinError(ctypes.get_last_error())
try:
    if not u.PostMessageW(state['hwnd'],0x112,0xf060,0):raise ctypes.WinError(ctypes.get_last_error())
    deadline=time.monotonic()+15
    while k.WaitForSingleObject(h,100)==258:
        if time.monotonic()>deadline:raise RuntimeError('Window may be asking for confirmation; inspect UI')
    code=W.DWORD()
    if not k.GetExitCodeProcess(h,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
    report['exitCode']=hex(code.value)
finally:
    k.CloseHandle(h);(ROOT/'diagnostics-v2'/f'system-close-{state["pid"]}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
