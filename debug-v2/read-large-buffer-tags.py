"""Read-only tag counts in the game's largest private allocation; no raw dump."""
import ctypes,json,runpy,time,collections,math,struct
from ctypes import wintypes as W
from harness import ROOT,identify
layout=runpy.run_path(str(ROOT/'debug-v2/read-va-layout.py'))['report'];pid=identify();assert pid==layout['pid']
allocation=next(a for a in layout['allocations'] if a['type']==0x20000);assert allocation['committed']<=512*1024**2
k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.CloseHandle.argtypes=[W.HANDLE]
k.ReadProcessMemory.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)];k.ReadProcessMemory.restype=W.BOOL
handle=k.OpenProcess(0x1410,False,pid);assert handle
tags=[b'ARIA-WIDE-1',b'KEYINPUT',b'CPU',b'VRAM',b'HEAP'];counts={t.decode():0 for t in tags};samples=[];histograms=[]
try:
    for region in layout['regions']:
        if region['allocation']!=allocation['base'] or region['state']!=0x1000 or region['protect']&0x101:continue
        tail=b''
        for offset in range(0,region['size'],1024**2):
            size=min(1024**2,region['size']-offset);buffer=ctypes.create_string_buffer(size);used=ctypes.c_size_t()
            if not k.ReadProcessMemory(handle,ctypes.c_void_p(region['base']+offset),buffer,size,ctypes.byref(used)):raise ctypes.WinError(ctypes.get_last_error())
            data=tail+buffer.raw[:used.value];row={t.decode():data.count(t) for t in tags}
            if offset%(32*1024**2)==0:
                h=collections.Counter(buffer.raw[:used.value]);entropy=-sum((n/used.value)*math.log2(n/used.value) for n in h.values())
                histograms.append({'offset':region['base']+offset-allocation['base'],'zeroFraction':h[0]/used.value,'entropy':entropy,'firstU32':list(struct.unpack_from('<8I',buffer.raw))})
            for name,n in row.items():counts[name]+=n
            if any(row.values()):samples.append({'offset':region['base']+offset-allocation['base'],'counts':row})
            tail=data[-10:]
    report={'pid':pid,'time':time.time(),'allocation':allocation,'counts':counts,'samples':samples,'histograms':histograms}
    path=ROOT/f'diagnostics-v2/large-buffer-tags-{pid}-{int(time.time())}.json';path.write_text(json.dumps(report,indent=2));print(json.dumps({'report':str(path),'allocation':allocation,'counts':counts,'histograms':histograms}))
finally:k.CloseHandle(handle)
