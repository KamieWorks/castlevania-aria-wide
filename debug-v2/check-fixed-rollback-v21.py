"""Item 1: disabled optional fixed-room renderer stays native after old states."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify
pid=identify();tmp=debug_root()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'before':hashes(),'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'ini':(EXE.parent/'AriaWide.ini').read_text(),'samples':[]}
assert 'ExtendFixedRooms=0' in report['ini']
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'fixed-rollback-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/fixed-rollback-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user',str(tmp/'regressions-user-slot1').replace('\\','/'))
        p.capture('regressions-user-slot1',True,at_present=True)
        try:
            for fixture,fixed in [('chaos-boss',True),('julius-save-room',True),('user-slot3-right-edge',False)]:
                p.call('stateimport',fixture,str(tmp/fixture).replace('\\','/'));p.call('stateload',fixture);time.sleep(.2)
                label='v21-rollback-'+fixture;meta=p.capture(label,True,at_present=True)
                raw=(ROOT/f'private-v2/captures/{label}.ppu').read_bytes();frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
                assert int.from_bytes(raw[0x2205c:0x22060],'little')==0
                native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
                actual=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
                left=24 if fixed else meta['viewport']['left']
                assert np.array_equal(native,actual[1:161,left:left+240])
                if fixed:
                    assert not meta['viewport']['expanded']
                    assert not np.count_nonzero(actual[:,:24]) and not np.count_nonzero(actual[:,264:])
                else:assert meta['viewport']['expanded'] and left==48
                report['samples'].append({'fixture':fixture,'fixed':fixed,'viewport':meta['viewport'],'centerEqual':True,'sideNonzero':[int(np.count_nonzero(actual[:,:24])),int(np.count_nonzero(actual[:,264:]))]})
        finally:p.call('stateload','user',False)
    report['passed']=True
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0'
    (ROOT/f'diagnostics-v2/fixed-rollback-v21-{pid}-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
assert report['passed']
