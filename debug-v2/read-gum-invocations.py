"""Read-only attribution of the observed Frida 17.23.2 x86 invocation arrays.

Exact agent disassembly verifies entry size 0x8e0, function at +0x18, and
function_ctx->function_address at +0. A candidate must satisfy both pointers.
No hooks, RPCs or game input are installed by this observer.
"""
import ctypes,json,runpy,time,struct,collections
from ctypes import wintypes as W
from harness import ROOT,identify
layout=runpy.run_path(str(ROOT/'debug-v2/read-va-layout.py'))['report'];pid=identify();assert pid==layout['pid']
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.CloseHandle.argtypes=[W.HANDLE]
k.ReadProcessMemory.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
class Module(ctypes.Structure):
    _fields_=[('size',W.DWORD),('moduleId',W.DWORD),('processId',W.DWORD),('globalUses',W.DWORD),('processUses',W.DWORD),('base',ctypes.c_void_p),('bytes',W.DWORD),('handle',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]
k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
k.Module32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(Module)];k.Module32NextW.argtypes=[W.HANDLE,ctypes.POINTER(Module)]
snapshot=k.CreateToolhelp32Snapshot(0x18,pid);assert snapshot not in (None,ctypes.c_void_p(-1).value)
modules=[];m=Module();m.size=ctypes.sizeof(m)
try:
    ok=k.Module32FirstW(snapshot,ctypes.byref(m))
    while ok:modules.append({'name':m.name,'base':m.base,'size':m.bytes});ok=k.Module32NextW(snapshot,ctypes.byref(m))
finally:k.CloseHandle(snapshot)
def label(address):
    for m in modules:
        if m['base']<=address<m['base']+m['size']:return m['name']+'+'+hex(address-m['base'])
    return hex(address)
handle=k.OpenProcess(0x1410,False,pid);assert handle
def read(address,size):
    b=ctypes.create_string_buffer(size);n=ctypes.c_size_t()
    if not k.ReadProcessMemory(handle,ctypes.c_void_p(address),b,size,ctypes.byref(n)) or n.value!=size:raise OSError(ctypes.get_last_error())
    return b.raw
found=[]
try:
    for allocation in layout['allocations']:
        capacity=allocation['committed']-0x10000
        if allocation['type']!=0x20000 or allocation['reserved'] or capacity<0x100000 or capacity&(capacity-1):continue
        for offset in (8,16):
            try:
                first=read(allocation['base']+offset,0x28);ctx,caller,sp=struct.unpack_from('<III',first);function=struct.unpack_from('<I',first,0x18)[0]
                if not ctx or not function or struct.unpack('<I',read(ctx,4))[0]!=function or '+' not in label(function):continue
                data=read(allocation['base']+offset,min(128*0x8e0,capacity));entries=[]
                for i in range(len(data)//0x8e0):
                    pos=i*0x8e0;ctx,caller,sp=struct.unpack_from('<III',data,pos);function=struct.unpack_from('<I',data,pos+0x18)[0]
                    if not ctx:break
                    entries.append({'index':i,'functionContext':hex(ctx),'function':label(function),'caller':label(caller),'stackAddress':hex(sp),'stackId':hex(struct.unpack_from('<Q',data,pos+0x10)[0])})
                found.append({'allocation':allocation,'payloadOffset':offset,'sampleCount':len(entries),'functions':dict(collections.Counter(e['function'] for e in entries)),'entries':entries[:12]})
            except OSError:continue
    report={'pid':pid,'time':time.time(),'agentVersion':'17.23.2','entrySize':0x8e0,'arrays':found}
    path=ROOT/f'diagnostics-v2/gum-invocations-{pid}-{int(time.time())}.json';path.write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:k.CloseHandle(handle)
