"""Read slot 2 HUD OAM through background input; restore runtime state on exit."""
from debug_config import profile_root
import hashlib,json,os,pathlib,struct,subprocess,sys,time
from harness import Probe,ROOT,EXE,identify
work=pathlib.Path(sys.argv[1]);assert work.is_dir()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'before':hashes(),'samples':[]};pid=identify()
backup=ROOT/'private-v2/checkpoints/v27-before';backup.mkdir(exist_ok=True)
for f in ['d3d9.dll','aria-wide-test.log']:
 p=EXE.parent/f
 if p.exists() and not (backup/f).exists():(backup/f).write_bytes(p.read_bytes())
for p in remote.iterdir():
 if p.is_file() and not (backup/p.name).exists():(backup/p.name).write_bytes(p.read_bytes())
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(work/'guard').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(work/'guard-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
 subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','2'],check=True,timeout=110)
 with Probe() as p:
  p.call('statesave','user')
  try:
   p.call('romdump',str(work/'running-rom.gba').replace('\\','/'))
   q=p.call('roompointer',0,10);door=next(d for d in q['doors'] if d['x']==-1 and d['y']==0)
   p.call('debugdoor',door['i'],q['target']);p.call('debugentry',q['target'],270,191)
   p.call('debugposition',24,191);p.call('pulse',[203],650);time.sleep(.3);p.call('restoredoors')
   for label,key in [('wide',None),('s1',31),('s2',31),('s3',31),('s4',31),('a',30),('tab',15)]:
    if key:p.call('pulse',[key],100);time.sleep(.2)
    prefix=work/label;m=p.call('capturescanpresent',str(prefix).replace('\\','/'),True)
    b=pathlib.Path(str(prefix)+'.scan.ppu').read_bytes();oam=[]
    for o in range(128):
     a0,a1,a2=struct.unpack_from('<3H',b,0x20000+8*o)
     if (a0&255)<40 and (a1&511)<240 and not (a0&0x300)==0x200:oam.append({'index':o,'a0':hex(a0),'a1':hex(a1),'a2':hex(a2)})
    report['samples'].append({'label':label,'meta':m,'topOam':oam});print(json.dumps(report['samples'][-1]),flush=True)
  finally:p.call('restoredoors');p.call('stateload','user',False)
finally:
 subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=40);guard.wait(timeout=15)
 report['after']=hashes();assert report['before']==report['after']
 report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
 (ROOT/'diagnostics-v2/julius-v27/discovery.json').write_text(json.dumps(report,indent=2))
