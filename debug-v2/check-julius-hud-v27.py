"""Compare slot-2 subweapon HUD against independently isolated native raster.

Only background native inputs and reversible diagnostic positioning are used.
No ROM, SRAM, achievement or profile writes are forwarded to Steam.
"""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time
import numpy as np
from PIL import Image
from harness import Probe,ROOT,EXE,identify
ap=argparse.ArgumentParser();ap.add_argument('--scratch',type=pathlib.Path,required=True);ap.add_argument('--baseline',action='store_true');ap.add_argument('--variant',default='chinese',choices=['japanese','chinese']);args=ap.parse_args()
work=args.scratch.resolve();assert work.is_dir()
tmp=debug_root()
pid=identify();tag=f'julius-v27-{args.variant}-{pid}';out=ROOT/'diagnostics-v2/julius-v27';out.mkdir(exist_ok=True)
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
def path(p):return str(p).replace('\\','/')
def rgb(a):
 v=np.stack([(a>>n)&31 for n in [0,5,10]],axis=-1).astype(np.uint8);return Image.fromarray((v<<3)|(v>>2))
report={'pid':pid,'variant':args.variant,'baseline':args.baseline,'before':hashes(),'dllSHA256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'samples':[],'tuples':[]}
def save():(out/(tag+'.json')).write_text(json.dumps(report,indent=2))
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),path(work/(tag+'-guard'))],stdout=subprocess.PIPE,stderr=open(work/'guard-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
 subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','2'],check=True,timeout=110)
 with Probe() as p:
  p.call('statesave','user')
  try:
   initial=p.call('capturepresent',path(work/(tag+'-fixed')),True)
   assert [initial['area'],initial['room']]==[0,14] and not initial['viewport']['expanded'],initial
   report['fixedRoomCentered']=True
   q=p.call('roompointer',0,10);door=next(d for d in q['doors'] if d['x']==-1 and d['y']==0)
   p.call('debugdoor',door['i'],q['target']);p.call('debugentry',q['target'],270,191)
   p.call('debugposition',24,191);p.call('pulse',[203],650);time.sleep(.3);p.call('restoredoors')
   p.call('statesave','wide')
   def check(label,expected):
    prefix=work/(tag+'-'+label);m=p.call('capturescanpresent',path(prefix),True)
    assert m['playState']==1 and m['viewport']['expanded'] and m['viewport']['left']==expected,m
    source=bytearray(pathlib.Path(str(prefix)+'.scan.ppu').read_bytes());fullSource=source[:]
    tuples=[list(struct.unpack_from('<3H',source,0x20000+8*i)) for i in [0,1]]
    for t in tuples:
     if t not in report['tuples']:report['tuples'].append(t)
    # The first two native HUD entries are the weapon and its frame. They
    # are isolated by native OAM ordering, independently of patch predicates.
    assert tuples[1][0]==4 and tuples[1][1]==0x5070 and tuples[1][2]&1023==0x2d6,tuples
    for o in range(2,128):struct.pack_into('<H',source,0x20000+8*o,0x200)
    for off in [0x20800,0x21fe8,0x22048]:
     struct.pack_into('<H',source,off,struct.unpack_from('<H',source,off)[0]&~0xf00)
    struct.pack_into('<H',source,0x20400,0);struct.pack_into('<H',source,0x22038,0);struct.pack_into('<I',source,0x5f46c,0)
    for x in range(240):
     for bg in range(4):struct.pack_into('<I',source,0x20c00+x*20+bg*4,0x80000000)
    fixture=pathlib.Path(str(prefix)+'.hud.ppu');fixture.write_bytes(source)
    p.call('renderfile',path(prefix)+'-native',path(tmp/'render-objects.dll'),path(fixture),'RenderSnapshot')
    native=np.fromfile(str(prefix)+'-native.shift0.rgb555',dtype='<u2').reshape(160,240)&0x7fff
    actual=np.fromfile(str(prefix)+'.rgb555',dtype='<u2').reshape(162,288)[1:161]&0x7fff
    mask=native!=0;assert mask.sum()>80
    wrong=int(np.sum(actual[:,:240][mask]!=native[mask]))
    # Independent native BG0 + first five OAM entries also protect health,
    # MP bars and HP digits from an overly broad sprite correction.
    for o in range(5,128):struct.pack_into('<H',fullSource,0x20000+8*o,0x200)
    for off in [0x20800,0x21fe8,0x22048]:struct.pack_into('<H',fullSource,off,struct.unpack_from('<H',fullSource,off)[0]&~0xe00)
    struct.pack_into('<H',fullSource,0x20400,0);struct.pack_into('<H',fullSource,0x22038,0);struct.pack_into('<I',fullSource,0x5f46c,0)
    for x in range(240):
     for bg in range(1,4):struct.pack_into('<I',fullSource,0x20c00+x*20+bg*4,0x80000000)
    fixture.write_bytes(fullSource);p.call('renderfile',path(prefix)+'-allhud',path(tmp/'render-objects.dll'),path(fixture),'RenderSnapshot')
    allhud=np.fromfile(str(prefix)+'-allhud.shift0.rgb555',dtype='<u2').reshape(160,240)&0x7fff
    health=allhud[:35,:144];hm=health!=0;assert hm.sum()>500
    hudWrong=int(np.sum(actual[:35,:144][hm]!=health[hm]))
    row={'label':label,'viewport':m['viewport'],'iconTuples':tuples,'pixels':int(mask.sum()),'wrongPixels':wrong,'hudPixels':int(hm.sum()),'hudWrongPixels':hudWrong};report['samples'].append(row);save()
    if label.endswith('0') or wrong:rgb(actual).resize((1152,640),Image.Resampling.NEAREST).save(out/(tag+'-'+label+'.png'))
    print(json.dumps(row),flush=True)
    return native
   for label,x,expected in [('left',70,0),('middle',270,24),('right',486,48)]:
    p.call('stateload','wide');p.call('debugmove',x,191);time.sleep(.3)
    for weapon in range(4):
     if weapon:p.call('pulse',[31],100)
     for frame in range(4):
      time.sleep(.09);check(f'{label}-weapon{weapon}-frame{frame}',expected)
   # A map round-trip and state restore must retain native centered UI.
   p.call('pulse',[15],100);time.sleep(.3)
   menu=p.call('capturepresent',path(work/(tag+'-map')),False);assert not menu['viewport']['expanded'] and menu['playState']==4
   p.call('pulse',[15],100);time.sleep(.3)
   p.call('stateload','wide');time.sleep(.2);native=check('state-roundtrip-frame0',24)
   report['motion']=[]
   if not args.baseline:
    for direction,x,key in [('left',177,203),('right',335,205)]:
     p.call('stateload','wide');p.call('debugmove',x,191);time.sleep(.2)
     prefix=work/(tag+'-motion-'+direction)
     p.call('denseframes',path(prefix),72,[key],1100,False)
     rows=json.loads(pathlib.Path(str(prefix)+'.frames.json').read_text())
     frames=np.fromfile(str(prefix)+'.frames.rgb555',dtype='<u2').reshape(72,162,288)[:,1:161]&0x7fff
     mask=native!=0;wrong=[int(np.sum(a[:,:240][mask]!=native[mask])) for a in frames]
     report['motion'].append({'direction':direction,'frames':72,'pixels':int(mask.sum())*72,'wrongPixels':sum(wrong),'viewportOffsets':sorted({r['viewport']['left'] for r in rows})})
     assert sum(wrong)==0,report['motion'][-1]
   report['mapCentered']=True;report['pixels']=sum(r['pixels'] for r in report['samples']);report['wrongPixels']=sum(r['wrongPixels'] for r in report['samples'])
   report['passed']=report['wrongPixels']==0 and all(r['hudWrongPixels']==0 for r in report['samples']) and {r['viewport']['left'] for r in report['samples']}=={0,24,48}
  finally:p.call('restoredoors');p.call('stateload','user',False)
finally:
 close=subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],timeout=40)
 guard.wait(timeout=15)
 report['after']=hashes();report['savesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text());report['passed']=report.get('passed',False) and report['savesUnchanged'] and report['exit']['exitCode']=='0x0';save()
 print(json.dumps({k:v for k,v in report.items() if k not in ['samples','tuples','before','after']}),flush=True)
if not args.baseline:assert report['passed']
