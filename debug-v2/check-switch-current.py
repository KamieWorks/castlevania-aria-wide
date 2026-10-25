"""Real collection Aria/Harmony/Aria selection with the cold player DLL."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,runpy,subprocess,sys,time
import numpy as np
from PIL import Image
from harness import Probe,ROOT,EXE,identify
pid=identify();tmp=debug_root();directory=tmp/f'switch-current-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes()}
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/switch-current-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
def shot(label):subprocess.run([sys.executable,str(ROOT/'debug-v2/backbuffer-shot.py'),label],check=True,timeout=18)
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    window=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
    with Probe() as p:
        report['start']=p.call('lifecycle')
        def ui(keys):
            r=p.call('uipulse',keys,100,window['hwnd']);print(json.dumps({'ui':keys,**r}),flush=True);assert r['forcedCalls']>0,r;time.sleep(.6)
        def cards():
            ui([59]);time.sleep(1);shot('switch-current-pause-gate')
            pause=np.asarray(Image.open(ROOT/'diagnostics-v2/switch-current-pause-gate.png').convert('RGB'))
            left=float(pause[775:800,175:470].mean());right=float(pause[775:800,565:865].mean())
            if right>150 and left<100:ui([203])
            elif not(left>150 and right<100):raise RuntimeError(f'Unexpected pause selection: {left}/{right}')
            ui([44]);time.sleep(1);shot('switch-current-card-gate')
            template=np.asarray(Image.open(ROOT/'diagnostics-v2/switch-current-cards-aria.png').convert('RGB'))[40:215,600:1250].astype('int16')
            mask=np.min(template,axis=2)>175
            def score():
                observed=np.asarray(Image.open(ROOT/'diagnostics-v2/switch-current-card-gate.png').convert('RGB'))[40:215,600:1250].astype('int16')
                return float(np.mean(np.max(np.abs(template-observed),axis=2)[mask]<25))
            if score()<=.8:ui([44]);time.sleep(2);shot('switch-current-card-gate')
            assert score()>.8,{'cardGateScore':score()}
        def wait(code):
            deadline=time.monotonic()+18
            while time.monotonic()<deadline:
                if p.call('romcode')==code:return
                time.sleep(.2)
            raise RuntimeError(f'Did not reach ROM {code}; actual {p.call("romcode")}')
        cards();shot('switch-current-cards-aria');ui([203]);shot('switch-current-harmony-selected');ui([44]);wait('ACHJ');time.sleep(2);ui([44]);time.sleep(2)
        m=p.capture('switch-current-harmony',True);report['harmony']={'frame':m,'lifecycle':p.call('lifecycle')}
        assert [m['width'],m['height'],m['pitch']]==[240,160,480],m
        assert report['harmony']['lifecycle']['activeContext']==0 and report['harmony']['lifecycle']['destroyed']>=1,report
        cards();shot('switch-current-cards-harmony');ui([205]);ui([44]);wait('A2CJ');time.sleep(1)
        m=p.capture('switch-current-aria-returned',True);report['returned']={'frame':m,'lifecycle':p.call('lifecycle')}
        assert [m['width'],m['height']]==[288,162] and report['returned']['lifecycle']['activeContext']!=0,report
        shot('switch-current-aria-client')
        report['passed']=True
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    (ROOT/'diagnostics-v2/switch-current-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:report.get(k) for k in ['pid','passed','realSavesUnchanged','exit']}))
assert report.get('passed') and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0',report
