"""Exercise the nonzero cloud OAM cache at both wide-camera limits."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,struct,subprocess,sys,time
from harness import Probe,ROOT,EXE,identify
pid=identify();tmp=debug_root();scratch=pathlib.Path(sys.argv[1]).resolve();assert scratch.is_dir() and not scratch.is_symlink()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'cases':[]}
out=ROOT/f'diagnostics-v2/cloud-state-v26-{pid}-check.json'
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'cloud-state-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/cloud-state-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
def cache(prefix):
 records=json.loads(pathlib.Path(str(prefix)+'.state.json').read_text());record=next(r for r in records if r['name']=='ARIA-WIDE-1')
 data=pathlib.Path(str(prefix)+'.state.bin').read_bytes()[record['offset']:record['offset']+record['size']]
 assert len(data)==95388 and struct.unpack_from('<II',data)==(0x31495741,9)
 count=struct.unpack_from('<I',data,92184)[0];corr=struct.unpack_from('<128i',data,94876)
 assert count==4 and sum(c!=0 for c in corr)==6 and max(map(abs,corr))<=23
 return data,{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'actors':count,'correctedPieces':sum(c!=0 for c in corr)}
try:
 subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
 with Probe() as p:
  p.call('statesave','user');p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'))
  try:
   for side,x in [('left',70),('right',450)]:
    p.call('stateload','wide');m=p.capture('cloud-state-source',True,at_present=True)
    p.call('debugmove',x,int(m['cameraY']+m['playerY']));time.sleep(.3)
    a=scratch/f'{side}-before';b=scratch/f'{side}-after'
    p.call('statesave',side,str(a).replace('\\','/'));before,info=cache(a)
    p.call('pulse',[205 if side=='left' else 203],250)
    p.call('statereloadsave',side,side+'-copy');comparison=p.call('statecompare',side,side+'-copy')
    assert not any(c['name']=='ARIA-WIDE-1' for c in comparison['changes'])
    p.call('stateload',side);m=p.capture('cloud-state-v26-'+side,True,at_present=True)
    assert m['viewport']['left']==(0 if side=='left' else 48),m
    report['cases'].append({'side':side,**info,'roundtripEqual':True,'viewport':m['viewport'],'otherNativeRecordsChanged':comparison['changes']})
   report['passed']=True
  finally:p.call('stateload','user',False)
finally:
 subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
 report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text());report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0'
 out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
assert report['passed']
