"""Read-only 32-bit virtual-allocation metadata for the exact game process."""
import ctypes,json,pathlib,time
from ctypes import wintypes as W
from harness import identify,ROOT
pid=identify();k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.CloseHandle.argtypes=[W.HANDLE]
k.VirtualQueryEx.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t];k.VirtualQueryEx.restype=ctypes.c_size_t
class Region(ctypes.Structure):
    _fields_=[('base',ctypes.c_void_p),('allocation',ctypes.c_void_p),('allocationProtect',W.DWORD),('partition',W.WORD),('size',ctypes.c_size_t),('state',W.DWORD),('protect',W.DWORD),('type',W.DWORD)]
handle=k.OpenProcess(0x1410,False,pid);assert handle,ctypes.get_last_error()
try:
    address=0;allocations={};regions=[]
    while address<0x80000000:
        r=Region()
        if not k.VirtualQueryEx(handle,ctypes.c_void_p(address),ctypes.byref(r),ctypes.sizeof(r)):break
        base=r.base or 0;end=min(0x80000000,base+r.size)
        if end<=address:break
        row={'base':base,'allocation':r.allocation or 0,'size':end-address,'state':r.state,'protect':r.protect,'type':r.type};regions.append(row)
        if r.allocation:
            a=allocations.setdefault(r.allocation,{'base':r.allocation,'committed':0,'reserved':0,'type':r.type})
            a['committed' if r.state==0x1000 else 'reserved']+=end-address
        address=end
    report={'pid':pid,'time':time.time(),'regions':regions,'allocations':sorted(allocations.values(),key=lambda a:a['committed'],reverse=True)}
    path=ROOT/f'diagnostics-v2/virtual-layout-{pid}-{int(time.time())}.json';path.write_text(json.dumps(report,indent=2))
    print(json.dumps({'pid':pid,'report':str(path),'largest':report['allocations'][:12]}))
finally:k.CloseHandle(handle)
