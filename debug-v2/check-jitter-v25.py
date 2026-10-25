"""Capture every consecutive emulator frame while holding a direction at an edge."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from PIL import Image
from harness import Probe,ROOT,EXE,identify
ap=argparse.ArgumentParser();ap.add_argument('--baseline',action='store_true');ap.add_argument('--version',default='v25',choices=['v25','v26']);args=ap.parse_args()
pid=identify();tmp=debug_root();version='v24' if args.baseline else args.version
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'baseline':args.baseline,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'cases':[]}
out=ROOT/f'diagnostics-v2/jitter-{version}-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2))
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'jitter-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/jitter-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user')
        for fixture in ['slot1-hud-info','v8-wide']:p.call('stateimport',fixture,str(tmp/fixture).replace('\\','/'))
        try:
            for fixture in ['slot1-hud-info','v8-wide']:
                for direction,x,key,limit in [('right',335,205,224),('left',177,203,0)]:
                    p.call('stateload',fixture);m=p.capture('dense-source',True,at_present=True)
                    p.call('debugmove',x,int(m['cameraY']+m['playerY']));time.sleep(.3)
                    prefix=tmp/f'dense-{pid}-{fixture}-{direction}'
                    result=p.call('denseframes',str(prefix).replace('\\','/'),96,[key],1100)
                    rows=json.loads(pathlib.Path(str(prefix)+'.frames.json').read_text())
                    pixels=np.fromfile(str(prefix)+'.frames.rgb555',dtype='<u2').reshape(96,162,288)[:,1:161]&0x7fff
                    errors=[];clamped=[]
                    for i,r in enumerate(rows):
                        expected=max(0,min(224,r['rasterCamera']-24));r['expectedWide']=expected
                        if r['rasterWideCamera']!=expected:errors.append(i)
                        if expected==limit:clamped.append(i)
                    assert len(clamped)>15,(fixture,direction,len(clamped))
                    differences=[int(np.sum(pixels[a,40:88]!=pixels[b,40:88])) for a,b in zip(clamped,clamped[1:]) if b==a+1]
                    bg=3 if fixture=='slot1-hud-info' else 2
                    origins=[(rows[i]['scroll'][bg]+rows[i]['corrections'][bg]-rows[i]['viewport']['left'])&511 for i in clamped] if rows[0]['corrections'] is not None else []
                    row={'fixture':fixture,'direction':direction,'frames':96,'phaseErrorFrames':errors,'clampedFrames':len(clamped),'changingStaticPixelPairs':sum(n>0 for n in differences) if fixture=='slot1-hud-info' else None,'maxPixelDifference':max(differences) if fixture=='slot1-hud-info' else None,'backgroundOrigins':sorted(set(origins)),'framePrefix':str(prefix),'telemetry':rows}
                    report['cases'].append(row);save();print(json.dumps({k:v for k,v in row.items() if k!='telemetry'}),flush=True)
                    directory=ROOT/f'diagnostics-v2/dense-{pid}-{fixture}-{direction}';directory.mkdir(exist_ok=True)
                    for i,frame in enumerate(pixels):
                        rgb=np.stack([(frame>>n)&31 for n in [0,5,10]],axis=-1).astype(np.uint8);rgb=(rgb<<3)|(rgb>>2)
                        Image.fromarray(rgb).save(directory/f'{i:03}.png')
            if args.baseline:report['passed']=any(c['phaseErrorFrames'] for c in report['cases']) and any(c['changingStaticPixelPairs'] for c in report['cases'] if c['fixture']=='slot1-hud-info')
            else:report['passed']=all(not c['phaseErrorFrames'] and len(c['backgroundOrigins'])==1 and (c['changingStaticPixelPairs']==0 if c['fixture']=='slot1-hud-info' else True) for c in report['cases'])
        finally:p.call('stateload','user',False)
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0';save();print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)
assert report['passed']
