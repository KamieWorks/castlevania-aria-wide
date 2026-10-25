import runpy,ctypes,time,json
from ctypes import wintypes as W
from harness import ROOT,Probe
s=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'));hwnd=s['hwnd']
u=ctypes.WinDLL('user32',use_last_error=True);u.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT];u.SetWindowPos.restype=W.BOOL
results=[]
with Probe() as p:
    before=p.call('stats');start=time.perf_counter();time.sleep(4);after=p.call('stats');elapsed=time.perf_counter()-start
    results.append({'type':'frame-rate','start':before,'end':after,'elapsed':elapsed,'fps':(after['frames']-before['frames'])/elapsed})
    try:
        if not u.SetWindowPos(hwnd,None,0,0,1280,800,0x16):raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(1)
        p.capture('resized-window',True);results.append({'type':'resized','status':p.call('status')})
    finally:
        u.SetWindowPos(hwnd,None,0,0,s['w'],s['h'],0x16);time.sleep(.8)
    p.capture('restored-window',True);results.append({'type':'restored','status':p.call('status')})
print(json.dumps(results,indent=2));(ROOT/'diagnostics-v2/resize-test.json').write_text(json.dumps(results,indent=2))
