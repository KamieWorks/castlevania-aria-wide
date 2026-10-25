"""Bounded Boss Rush idle/combat diagnosis with native second-chance capture."""
from debug_config import profile_root, debug_root, debugger_exe
import argparse,ctypes,hashlib,json,os,pathlib,re,subprocess,sys,time
from ctypes import wintypes as W
from harness import Probe,ROOT,EXE,identify
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=1200);parser.add_argument('--approach',action='store_true');args=parser.parse_args();assert 30<=args.seconds<=1800
pid=identify();tmp=debug_root();directory=tmp/f'bossrush-long-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'secondsRequested':args.seconds,'approach':args.approach,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'samples':[]}
k=ctypes.WinDLL('kernel32',use_last_error=True);ps=ctypes.WinDLL('psapi',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;k.CloseHandle.argtypes=[W.HANDLE]
k.DebugBreakProcess.argtypes=[W.HANDLE];k.DebugBreakProcess.restype=W.BOOL
k.VirtualQueryEx.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t];k.VirtualQueryEx.restype=ctypes.c_size_t
class MemoryInfo(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ('peakWorking','working','peakPaged','paged','peakNonPaged','nonPaged','pagefile','peakPagefile','private')]
class Region(ctypes.Structure):
    _fields_=[('base',ctypes.c_void_p),('allocation',ctypes.c_void_p),('allocationProtect',W.DWORD),('partition',W.WORD),('size',ctypes.c_size_t),('state',W.DWORD),('protect',W.DWORD),('type',W.DWORD)]
ps.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.POINTER(MemoryInfo),W.DWORD];ps.GetProcessMemoryInfo.restype=W.BOOL
handle=k.OpenProcess(0x1410,False,pid);assert handle,ctypes.get_last_error()
def memory():
    m=MemoryInfo();m.cb=ctypes.sizeof(m)
    if not ps.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):raise ctypes.WinError(ctypes.get_last_error())
    address=0;free=largest=reserved=0
    while address<0x80000000:
        r=Region();size=k.VirtualQueryEx(handle,ctypes.c_void_p(address),ctypes.byref(r),ctypes.sizeof(r))
        if not size:break
        base=r.base or 0;end=min(0x80000000,base+r.size)
        if end<=address:break
        if r.state==0x10000:free+=end-address;largest=max(largest,end-address)
        elif r.state==0x2000:reserved+=end-address
        address=end
    return {'private':m.private,'working':m.working,'freeBelow2GiB':free,'largestFreeRegion':largest,'reservedBelow2GiB':reserved}
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/bossrush-long-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
cdb=None
def observe_native():
    cdb_path=debugger_exe()
    native_log=tmp/f'bossrush-native-{pid}.log';native_dump=tmp/f'bossrush-native-{pid}.dmp'
    command_file=tmp/f'bossrush-native-{pid}.cmd'
    command_file.write_text(f'sxe -c ".dump /m /o {native_dump}; .exr -1; .ecxr; r; kv; gn" av\n.echo ARIA_CDB_READY\ng\n',encoding='ascii')
    observer_output=open(tmp/f'bossrush-native-{pid}-console.log','w')
    cdb=subprocess.Popen([str(cdb_path),'-p',str(pid),'-pd','-G','-y',str(tmp),'-logo',str(native_log),'-cf',str(command_file)],stdin=subprocess.PIPE,stdout=observer_output,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    deadline=time.monotonic()+20
    while not native_log.exists() or not re.search(r'^ARIA_CDB_READY\s*$',native_log.read_text(errors='replace'),re.M):
        if cdb.poll() is not None or time.monotonic()>deadline:raise RuntimeError(f'Native crash observer did not become ready (exit={cdb.poll()}); inspect its console log')
        time.sleep(.2)
    report['nativeObserver']={'pid':cdb.pid,'log':str(native_log),'dump':str(native_dump)}
    return cdb
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    with Probe() as p:
        # Attach only after all Frida agents are resident. Keep software
        # breakpoints out of ntdll/WOW64 syscall stubs during normal shutdown.
        cdb=observe_native()
        p.call('statesave','user');p.call('stateimport','source',str(tmp/'native-bossrush-start').replace('\\','/'));p.call('stateload','source')
        try:
            p.call('pulse',[205],1600);deadline=time.monotonic()+12
            while True:
                meta=p.capture('bossrush-long-entry',True,at_present=True);ram=(ROOT/'private-v2/captures/bossrush-long-entry.ewram').read_bytes()
                if int.from_bytes(ram[0x88:0x8c],'little')==0x084fb14c and meta['playState']==1:break
                if time.monotonic()>deadline:raise RuntimeError('Native first Boss Rush doorway did not settle')
                time.sleep(.3)
            assert int.from_bytes(ram[0x4cc:0x4d0],'little')&1,'Boss Rush flag not set'
            if args.approach:p.call('pulse',[205],2200)
            p.call('statewatch');start=time.monotonic();last_sample=start-10;index=0
            while time.monotonic()-start<args.seconds:
                if time.monotonic()-last_sample<10:time.sleep(.5);continue
                label=f'bossrush-long-{pid}-{index}'
                try:meta=p.capture(label,True,at_present=True)
                except Exception as e:
                    report['captureFailure']={'error':str(e),'time':time.time()}
                    for method in ('status','stats','lifecycle'):
                        try:report['captureFailure'][method]=p.call(method)
                        except Exception as inner:report['captureFailure'][method+'Error']=str(inner)
                    report['captureFailure']['memory']=memory()
                    (ROOT/f'diagnostics-v2/bossrush-long-{pid}-check.json').write_text(json.dumps(report,indent=2))
                    if cdb.poll() is None:
                        debug_handle=k.OpenProcess(0x1f0fff,False,pid)
                        try:
                            report['captureFailure']['debugBreak']=bool(debug_handle and k.DebugBreakProcess(debug_handle))
                            if report['captureFailure']['debugBreak']:
                                cdb.stdin.write(f'.dump /m {tmp}/bossrush-hang-{pid}.dmp\n~* kv\nr\nqd\n');cdb.stdin.flush()
                                try:cdb.wait(timeout=20)
                                except subprocess.TimeoutExpired:report['captureFailure']['observerDidNotDetach']=True
                        finally:
                            if debug_handle:k.CloseHandle(debug_handle)
                    raise
                ram=(ROOT/f'private-v2/captures/{label}.ewram').read_bytes();mem=memory()
                row={'elapsed':time.monotonic()-start,'mode':meta['gameMode'],'playState':meta['playState'],'header':hex(int.from_bytes(ram[0x88:0x8c],'little')),'hp':int.from_bytes(ram[0x1326e:0x13270],'little'),'hash':meta['frame_sha256'],'viewport':meta['viewport'],'memory':mem,'stats':p.call('stats'),'stateCalls':p.call('statecounts')}
                report['samples'].append(row);(ROOT/f'diagnostics-v2/bossrush-long-{pid}-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(row),flush=True);index+=1;last_sample=time.monotonic()
                if mem['freeBelow2GiB']<80*1024**2 or mem['largestFreeRegion']<8*1024**2:raise RuntimeError('Address-space diagnostic limit reached before a native allocation failure')
            report['boundedRunFinished']=True
        finally:
            try:p.call('stateload','user',False);report['userStateRestored']=True
            except Exception as e:report['restoreError']=str(e)
except Exception as e:report['error']=str(e);raise
finally:
    try:
        try:alive=identify()==pid
        except RuntimeError as e:
            if 'found []' not in str(e):raise
            alive=False
        if alive:subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30)
        guard.wait(timeout=15)
        if cdb and cdb.poll() is None:
            cdb.stdin.write('qd\n');cdb.stdin.flush()
            try:cdb.wait(timeout=10)
            except subprocess.TimeoutExpired:
                report['observerExitTimeout']=True;cdb.terminate();cdb.wait(timeout=10)
        report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];exit_path=ROOT/f'diagnostics-v2/game-exit-{pid}.json';report['exit']=json.loads(exit_path.read_text()) if exit_path.exists() else None
        report['passed']=report.get('boundedRunFinished',False) and report['realSavesUnchanged'] and report['exit'] and report['exit']['exitCode']=='0x0'
    finally:
        if 'after' not in report:
            report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after']
            exit_path=ROOT/f'diagnostics-v2/game-exit-{pid}.json';report['exit']=json.loads(exit_path.read_text()) if exit_path.exists() else None
        k.CloseHandle(handle);(ROOT/f'diagnostics-v2/bossrush-long-{pid}-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({'pid':pid,'passed':report.get('passed'),'exit':report.get('exit'),'error':report.get('error')}),flush=True)
