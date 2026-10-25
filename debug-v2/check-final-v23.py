"""Serial v23 render/history/menu regressions, scoped to the final binary."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify
ap=argparse.ArgumentParser();ap.add_argument('--version',default='v23',choices=['v23','v25','v26']);version=ap.parse_args().version
pid=identify();tmp=debug_root()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'tests':[],'fixedRooms':[]}
out=ROOT/f'diagnostics-v2/final-{version}-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2))
prefix=str(tmp/f'final-{version}-user-{pid}').replace('\\','/');saved=False
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'final-{version}-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/f'diagnostics-v2/final-{version}-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user',prefix);saved=True
        for fixture in ['chaos-boss','julius-save-room']:
            p.call('stateimport',fixture,str(tmp/fixture).replace('\\','/'));p.call('stateload',fixture);time.sleep(.2)
            label=f'{version}-fixed-{fixture}';m=p.capture(label,True,at_present=True)
            assert not m['viewport']['expanded'],m
            raw=(tmp/(label+'.ppu')).read_bytes();frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
            assert int.from_bytes(raw[0x2205c:0x22060],'little')==0
            native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
            output=np.fromfile(tmp/(label+'.rgb555'),dtype='<u2').reshape(162,288)
            assert np.array_equal(native,output[1:161,24:264])
            assert not np.count_nonzero(output[:,:24]) and not np.count_nonzero(output[:,264:])
            report['fixedRooms'].append({'fixture':fixture,'centerEqual':True,'sidePixels':0})
        p.call('stateload','user',False)
        # A second genuine room exercises the half-speed BG2, with native
        # objects masked by their hardware bounds so moving enemies cannot
        # be mistaken for camera drift. Blue castle pixels identify the BG.
        p.call('stateimport','half',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','half')
        m=p.capture(f'{version}-half-source',True,at_present=True)
        p.call('debugmove',335,int(m['cameraY']+m['playerY']));time.sleep(.3)
        half=[]
        for i in range(20):
            if i:p.call('pulse',[205],25)
            label=f'{version}-half-{i}';m=p.capture(label,True,at_present=True);v=m['viewport']
            assert [m['area'],m['room']]==[0,10],m
            ram=(tmp/(label+'.ewram')).read_bytes();assert ram[0xa078+2*28+24]==2
            pixels=np.fromfile(tmp/(label+'.rgb555'),dtype='<u2').reshape(162,288)[1:161]&0x7fff
            raw=(tmp/(label+'.ppu')).read_bytes();mask=np.ones((160,288),dtype=bool)
            dims=[[(8,8),(16,16),(32,32),(64,64)],[(16,8),(32,8),(32,16),(64,32)],[(8,16),(8,32),(16,32),(32,64)]]
            for o in range(128):
                a0,a1,a2=struct.unpack_from('<3H',raw,0x20000+o*8)
                if (a0,a1,a2)==(0,0x1e0,0) or a0&0x300==0x200 or a0>>14==3:continue
                w,h=dims[a0>>14][a1>>14];w*=2 if a0&0x300==0x300 else 1;h*=2 if a0&0x300==0x300 else 1
                x=(a1&511);x=x-512 if x>=256 else x;x+=v['left'];y=a0&255;y=y-256 if y>=160 else y
                mask[max(0,y-4):min(160,y+h+4),max(0,x-4):min(288,x+w+4)]=False
            half.append((m,pixels,mask))
            if v['left']==48:break
        pairs=[(a,b) for a in range(len(half)) for b in range(a+1,len(half)) if half[a][0]['viewport']['camera']-half[a][0]['viewport']['left']==half[b][0]['viewport']['camera']-half[b][0]['viewport']['left']==224 and half[b][0]['cameraX']-half[a][0]['cameraX']>=6]
        assert pairs,'No half-speed camera transition';a,b=max(pairs,key=lambda pair:half[pair[1]][0]['cameraX']-half[pair[0]][0]['cameraX'])
        pa,pb=half[a][1],half[b][1];mask=half[a][2]&half[b][2];mask[:40]=False;mask[88:]=False
        mask&=((pa>>10)&31)>(pa&31)+3;mask&=((pa>>10)&31)>((pa>>5)&31)+1
        assert int(mask.sum())>50,'No visible blue background sample'
        eq=float(np.mean(pa[mask]==pb[mask]));assert eq==1.0,eq
        report['halfSpeedParallax']={'a':a,'b':b,'backgroundPixels':int(mask.sum()),'equal':eq,'nativeCameraDelta':half[b][0]['cameraX']-half[a][0]['cameraX']};save()
    required=['check-edge-framing.py','check-unused-oam.py','check-edge-objects.py','check-blends.py','check-affine.py','check-affine-rooms.py','check-rewind.py','check-menus.py']
    for script in required:
        start=time.monotonic();result=subprocess.run([sys.executable,str(ROOT/'debug-v2'/script)],timeout=110,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (ROOT/f'diagnostics-v2/final-{version}-{pid}-{script}.log').write_bytes(result.stdout)
        print(json.dumps({'subprocessLog':f'final-{version}-{pid}-{script}.log'}),flush=True)
        row={'script':script,'exitCode':result.returncode,'seconds':time.monotonic()-start};report['tests'].append(row);save();print(json.dumps(row),flush=True)
        assert result.returncode==0,row
    report['passed']=True
finally:
    try:
        if saved:
            with Probe() as p:p.call('stateimport','user',prefix);p.call('stateload','user',False)
    finally:
        subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
        report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
        report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0';save();print(json.dumps(report),flush=True)
assert report['passed']
