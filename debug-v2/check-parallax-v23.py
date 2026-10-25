"""Real room camera-limit regression; keep autonomous background animation alive."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify,KEYS
ap=argparse.ArgumentParser();ap.add_argument('--baseline',action='store_true');args=ap.parse_args()
pid=identify();tmp=debug_root()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'baseline':args.baseline,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'samples':[]}
out=ROOT/f'diagnostics-v2/parallax-{"v22-baseline" if args.baseline else "v23"}-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2))
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'parallax-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/parallax-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user');p.call('stateimport','room',str(tmp/'slot1-hud-info').replace('\\','/'))
        try:
            p.call('stateload','room');p.call('debugmove',335,163);time.sleep(.5)
            arrays=[]
            for i in range(38):
                if i:p.call('pulse',[KEYS['right']],25);time.sleep(.1)
                label=f'parallax-{pid}-{i}';meta=p.capture(label,True,at_present=True)
                assert meta['area']==5 and meta['room']==6 and meta['viewport']['expanded'],meta
                v=meta['viewport'];ram=(tmp/(label+'.ewram')).read_bytes()
                raw=(tmp/(label+'.ppu')).read_bytes();scroll=struct.unpack_from('<H',raw,0x21ffc)[0]
                rasterCamera=v['camera']+((scroll-v['camera']+256)&511)-256
                row={'label':label,'camera':v['camera'],'left':v['left'],'wideCamera':v['camera']-v['left'],'rasterWideCamera':rasterCamera-v['left'],'cameraY':meta['cameraY'],'worldX':meta['cameraX']+meta['playerX'],'backgrounds':[{'method':ram[0xa078+bg*28+0x18],'xFP':struct.unpack_from('<i',ram,0xa078+bg*28+4)[0]} for bg in [2,3]]}
                report['samples'].append(row);save();print(json.dumps(row),flush=True)
                arrays.append(np.fromfile(tmp/(label+'.rgb555'),dtype='<u2').reshape(162,288)[1:161]&0x7fff)
                if v['left']==48 and i>15:break
            pairs=[]
            for a in range(len(arrays)):
                for b in range(a+1,len(arrays)):
                    ra,rb=report['samples'][a],report['samples'][b]
                    if ra['wideCamera']==rb['wideCamera']==ra['rasterWideCamera']==rb['rasterWideCamera']==224 and ra['cameraY']==rb['cameraY'] and rb['camera']-ra['camera']>=6:
                        # Character hair starts at y=94; use only static sky,
                        # moon and foreground masonry above that world object.
                        roiA,roiB=arrays[a][40:88],arrays[b][40:88]
                        pairs.append({'a':a,'b':b,'nativeCameraDelta':rb['camera']-ra['camera'],'equal':float(np.mean(roiA==roiB)),'differentPixels':int(np.sum(roiA!=roiB))})
            assert pairs,'Did not sample the native camera moving after the wide camera stopped'
            best=max(pairs,key=lambda x:x['nativeCameraDelta']);report['stoppedForegroundPair']=best
            report['freezeVerified']=best['equal']>.999
            report['baselineReproduced']=best['differentPixels']>100
            # With the camera idle, the native water effect must still animate.
            time.sleep(.2)
            first=p.capture(f'parallax-{pid}-idle-a',True,at_present=True);time.sleep(.25)
            second=p.capture(f'parallax-{pid}-idle-b',True,at_present=True)
            a=np.fromfile(tmp/f'parallax-{pid}-idle-a.rgb555',dtype='<u2').reshape(162,288)[1:161]&0x7fff
            b=np.fromfile(tmp/f'parallax-{pid}-idle-b.rgb555',dtype='<u2').reshape(162,288)[1:161]&0x7fff
            report['idleSkyEqual']=float(np.mean(a[40:88]==b[40:88]))
            report['idleWaterDifferentPixels']=int(np.sum(a[140:160]!=b[140:160]))
            p.call('debugmove',177,163);time.sleep(.3)
            leftFrames=[];leftRows=[]
            for i in range(16):
                if i:p.call('pulse',[KEYS['left']],25);time.sleep(.1)
                label=f'parallax-{pid}-left-{i}';m=p.capture(label,True,at_present=True);v=m['viewport']
                assert [m['area'],m['room']]==[5,6],m
                raw=(tmp/(label+'.ppu')).read_bytes();scroll=struct.unpack_from('<H',raw,0x21ffc)[0]
                rasterCamera=v['camera']+((scroll-v['camera']+256)&511)-256
                leftRows.append({'label':label,'camera':v['camera'],'left':v['left'],'wideCamera':v['camera']-v['left'],'rasterWideCamera':rasterCamera-v['left']})
                leftFrames.append(np.fromfile(tmp/(label+'.rgb555'),dtype='<u2').reshape(162,288)[41:89]&0x7fff)
                if v['left']==0:break
            lp=[{'a':a,'b':b,'nativeCameraDelta':leftRows[a]['camera']-leftRows[b]['camera'],'equal':float(np.mean(leftFrames[a]==leftFrames[b]))} for a in range(len(leftRows)) for b in range(a+1,len(leftRows)) if leftRows[a]['wideCamera']==leftRows[b]['wideCamera']==leftRows[a]['rasterWideCamera']==leftRows[b]['rasterWideCamera']==0 and leftRows[a]['camera']-leftRows[b]['camera']>=6]
            assert lp,'No left-edge camera transition';report['leftSamples']=leftRows
            report['leftStoppedForegroundPair']=max(lp,key=lambda x:x['nativeCameraDelta'])
            report['leftFreezeVerified']=report['leftStoppedForegroundPair']['equal']>.999
            report['passed']=report['baselineReproduced'] if args.baseline else report['freezeVerified'] and report['leftFreezeVerified'] and report['idleWaterDifferentPixels']>0
            print(json.dumps({k:v for k,v in report.items() if k not in ['samples','before']}),flush=True)
        finally:p.call('stateload','user',False)
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0';save();print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
assert report['passed']
