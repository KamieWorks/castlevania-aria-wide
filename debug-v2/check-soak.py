"""Bounded interactive rendering run, with private-state resets and no save-slot writes."""
from debug_config import debug_root
import argparse,ctypes,json,os,pathlib,time
from ctypes import wintypes as W
from harness import Probe,ROOT
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=120);parser.add_argument('--no-resets',action='store_true');a=parser.parse_args();assert 10<=a.seconds<=600
tmp=debug_root()
k=ctypes.WinDLL('kernel32',use_last_error=True);ps=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.CloseHandle.argtypes=[W.HANDLE]
class MemoryInfo(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ('peakWorking','working','peakPaged','paged','peakNonPaged','nonPaged','pagefile','peakPagefile','private')]
ps.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.POINTER(MemoryInfo),W.DWORD];ps.GetProcessMemoryInfo.restype=W.BOOL
def memory(handle):
    out=MemoryInfo();out.cb=ctypes.sizeof(out)
    if not ps.GetProcessMemoryInfo(handle,ctypes.byref(out),out.cb):raise ctypes.WinError(ctypes.get_last_error())
    return {'working':out.working,'private':out.private}
report={'durationRequested':a.seconds,'periodicFixtureResets':not a.no_resets,'samples':[]};handle=None
try:
    with Probe() as p:
        handle=k.OpenProcess(0x1010,False,p.pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'));p.call('statesave','safe')
        p.call('stateload','wide');p.call('statewatch');start=time.monotonic();lastReset=start;lastSample=start-10;index=0
        report['pid']=p.pid;report['start']=p.call('stats')
        try:
            while time.monotonic()-start<a.seconds:
                for keys,ms in [([203],550),([205],550),([44],100),([45],100)]:p.call('pulse',keys,ms)
                now=time.monotonic()
                if now-lastSample>=10:
                    label=f'soak-{a.seconds}-{index}';meta=p.capture(label,False)
                    sample={'elapsed':now-start,'frameHash':meta['frame_sha256'],'cameraX':meta['cameraX'],'stats':p.call('stats'),'status':p.call('status'),'memory':memory(handle)}
                    assert sample['status']['deviceLost']==0 and sample['status']['gameMode']==4,sample
                    report['samples'].append(sample);index+=1;lastSample=now;print(json.dumps(sample),flush=True)
                if not a.no_resets and now-lastReset>=15:p.call('stateload','wide');lastReset=now
            report['elapsed']=time.monotonic()-start;report['end']=p.call('stats')
            report['distinctCapturedFrames']=len({r['frameHash'] for r in report['samples']})
            report['nativeStateCallsDuringRun']=p.call('statecounts')
            if a.no_resets:assert report['nativeStateCallsDuringRun']['loads']==0,report
            report['passed']=report['distinctCapturedFrames']>=3;assert report['passed'],report
        finally:p.call('stateload','safe')
except Exception as e:
    report['error']=str(e);report['passed']=False;raise
finally:
    if handle:k.CloseHandle(handle)
    (ROOT/'diagnostics-v2'/f'soak-{a.seconds}-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
