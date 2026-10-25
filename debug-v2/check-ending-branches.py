"""Replay remaining retail ending branches under private save/stat isolation."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify
pid=identify();tmp=debug_root();directory=tmp/f'ending-branches-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'branches':[]}
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/ending-branches-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user');p.call('stateimport','soma',str(tmp/'soma-safe-room').replace('\\','/'))
        try:
            for kind in ['bad','julius']:
                p.call('stateload','soma');branch={'kind':kind,'trigger':p.call('nativeendingrequest',kind),'samples':[]};report['branches'].append(branch)
                start=time.monotonic();index=0
                while time.monotonic()-start<150:
                    time.sleep(1.5);label=f'ending-{kind}-v19-{index}';m=p.capture(label,True,at_present=True);event=p.call('endingstatus');index+=1
                    raw=(ROOT/f'private-v2/captures/{label}.ppu').read_bytes();i=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
                    native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+i*0x14000).reshape(160,256)[:,:240];out=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
                    left=m['viewport']['left'] if m['viewport']['expanded'] else 24
                    assert int.from_bytes(raw[0x2205c:0x22060],'little')==0 and np.array_equal(native,out[1:161,left:left+240]),label
                    row={'elapsed':time.monotonic()-start,'mode':m['gameMode'],'playState':m['playState'],'header':event['roomPointer'],'flags':event['eventFlags'],'centerEqual':True,'hash':m['frame_sha256']};branch['samples'].append(row)
                    if sum(s['mode']==6 for s in branch['samples'])>=3:break
                    p.call('pulse',[44],100)
                branch['reachedCredits']=sum(s['mode']==6 for s in branch['samples'])>=3
                branch['requestedHeaderSeen']=any(s['header']==branch['trigger']['targetHeader'] for s in branch['samples'])
                assert branch['reachedCredits'] and branch['requestedHeaderSeen'],branch
                print(json.dumps({'kind':kind,'samples':len(branch['samples']),'reachedCredits':True}),flush=True)
        finally:p.call('stateload','user',False)
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text());report['events']=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
    report['passed']=len(report['branches'])==2 and all(b.get('reachedCredits') for b in report['branches']) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0'
    (ROOT/'diagnostics-v2/ending-other-branches-v19-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'realSavesUnchanged':report['realSavesUnchanged'],'exit':report['exit']}),flush=True)
assert report['passed']
