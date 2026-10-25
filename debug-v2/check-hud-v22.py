"""Compare anchored HUD with a frozen, isolated native BG0/OAM reference."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify,KEYS
ap=argparse.ArgumentParser();ap.add_argument('--version',default='v22',choices=['v22','v23']);ap.add_argument('--actual',action='store_true');args=ap.parse_args()
pid=identify();tmp=debug_root()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'samples':[],'hits':[]}
out=ROOT/f'diagnostics-v2/hud-{args.version}-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2))
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'hud-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/hud-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user')
        p.call('stateimport','room',str(tmp/'slot1-hud-info').replace('\\','/'))
        p.call('stateimport','parent',str(tmp/'slot1-parent-enemy-info').replace('\\','/'))
        p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'))
        def check(label):
            meta=p.capture(label,True,at_present=True);assert meta['playState']==1 and meta['viewport']['expanded'],meta
            source=bytearray((tmp/(label+'.ppu')).read_bytes())
            def u16(o):return struct.unpack_from('<H',source,o)[0]
            for o in [0x20800,0x21fe8,0x22048]:struct.pack_into('<H',source,o,u16(o)&~0xe00)
            struct.pack_into('<H',source,0x20400,0);struct.pack_into('<I',source,0x5f46c,0)
            for x in range(240):
                for bg in range(1,4):struct.pack_into('<I',source,0x20c00+x*20+bg*4,0x80000000)
            for o in range(128):
                off=0x20000+o*8;a0,a1,a2=struct.unpack_from('<3H',source,off);x=a1&511
                digit=a0==6 and a1&~511==0 and 6<=x<=26 and (x-6)%5==0 and a2&0xfc00==0x7000 and 0x80<=a2&1023<=0x89
                if not digit:struct.pack_into('<H',source,off,(a0&~0x100)|0x200)
            path=tmp/(label+'-hud.ppu');path.write_bytes(source)
            p.call('renderfile',str(tmp/label).replace('\\','/'),str(tmp/'render-objects.dll').replace('\\','/'),str(path).replace('\\','/'),'RenderSnapshot')
            native=np.fromfile(tmp/(label+'.shift0.rgb555'),dtype='<u2').reshape(160,240)&0x7fff
            actual=np.fromfile(tmp/(label+'.rgb555'),dtype='<u2').reshape(162,288)[1:161]&0x7fff
            top=native[:35,:160];mask=top!=0;assert mask.sum()>500
            top_equal=float(np.mean(actual[:35,:160][mask]==top[mask]))
            bottom=native[120:];bottom_mask=bottom!=0
            right_equal=float(np.mean(actual[120:,48:288][bottom_mask]==bottom[bottom_mask])) if bottom_mask.any() else None
            row={'label':label,'viewport':meta['viewport'],'topPixels':int(mask.sum()),'topEqual':top_equal,'rightPixels':int(bottom_mask.sum()),'rightEqual':right_equal};report['samples'].append(row);save();print(json.dumps(row),flush=True)
            assert top_equal>.99,row
            if bottom_mask.any():assert right_equal>.99,row
            return meta,row
        try:
            if args.actual:
                # Start from the real new slot 1. Only native move/jump/melee
                # pulses precede this evidence; no notification RAM requests.
                p.call('stateload','user');p.call('pulse',[KEYS['right']],1800);time.sleep(1)
                for keys,ms in [('right+x',400),('right+z',700),('x',200),('right+x',400)]:
                    p.call('pulse',[KEYS[k] for k in keys.split('+')],ms)
                for i in range(30):
                    direction='right' if i<14 else 'left'
                    keys=direction+('+z' if i%3==0 else '+x')
                    p.call('pulse',[KEYS[k] for k in keys.split('+')],350)
                    label=f'hud-{args.version}-skeleton-{i}';meta=p.capture(label,True,at_present=True)
                    ram=(tmp/(label+'.ewram')).read_bytes();name=struct.unpack_from('<H',ram,0x420)[0]
                    if 605<=name<=716 and ram[0x422]>10 and ram[0x423]==0:
                        _,row=check(label+'-verified')
                        if row['rightPixels']>50:
                            report['actualSkeleton']={'nameId':name,'nativeInputOnly':True,'sample':row};break
                assert report.get('actualSkeleton'),'Native skeleton notification was not observed'
            for name,fixture,x,expected in [('left','wide',70,0),('middle','room',256,24),('right','room',470,48)]:
                p.call('stateload',fixture);m=p.capture('hud-position-source',True,at_present=True)
                p.call('debugmove',x,int(m['cameraY']+m['playerY']));time.sleep(.5)
                p.call('debugenemynotice',605);time.sleep(.15)
                check('hud-'+args.version+'-'+name)
                assert report['samples'][-1]['viewport']['left']==expected,report['samples'][-1]
                assert report['samples'][-1]['rightPixels']>50,report['samples'][-1]
            report['nativeNotificationRequest']=True
            report['enemyInfoVerified']=all(r['rightPixels']>50 and r['rightEqual']>.99 for r in report['samples'])
            report['passed']=report['enemyInfoVerified'] and {r['viewport']['left'] for r in report['samples']}=={0,24,48}
        finally:p.call('stateload','user',False)
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0';save();print(json.dumps(report),flush=True)
assert report['passed']
