"""Exercise one native windowed D3D9 Reset while preserving the user's state."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,subprocess,sys,time
import numpy as np
from PIL import Image
from harness import Probe,ROOT,EXE,identify
pid=identify();tmp=debug_root()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'before':hashes(),'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'coverage':'One synthetic Present failure followed by a real native Reset; existing windowed mode only.'}
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'reset-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/reset-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user')
        try:
            p.call('pulse',[203],1500);before=p.capture('reset-before',True,at_present=True)
            assert [before['area'],before['room'],before['viewport']['left']]==[0,5,48],before
            result=subprocess.run(['node',str(ROOT/'debug-v2/device-reset-once.mjs'),str(pid)],capture_output=True,text=True,timeout=22,check=True)
            (ROOT/f'diagnostics-v2/reset-native-{pid}.log').write_text(result.stdout+'\n'+result.stderr)
            native=json.loads(result.stdout.splitlines()[-1]);report['native']=native
            assert native.get('injected') and native.get('resetReturned') and native.get('afterFrames',0)>=60,native
            after=p.capture('reset-after',True,at_present=True);report['afterFrame']=after;report['status']=p.call('status')
            assert [after['width'],after['height'],after['pitch']]==[288,162,576],after
            assert [after['area'],after['room'],after['viewport']['left']]==[0,5,48],after
            assert report['status']['deviceLost']==0,report['status']
            raw=(ROOT/'private-v2/captures/reset-after.ppu').read_bytes();index=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
            assert int.from_bytes(raw[0x2205c:0x22060],'little')==0
            center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+index*0x14000).reshape(160,256)[:,:240]
            output=np.fromfile(ROOT/'private-v2/captures/reset-after.rgb555',dtype='<u2').reshape(162,288)
            assert np.array_equal(center,output[1:161,48:288]);report['centerEqual']=True
            subprocess.run([sys.executable,str(ROOT/'debug-v2/backbuffer-shot.py'),'reset-after-client'],check=True,timeout=18)
            client=np.asarray(Image.open(ROOT/'diagnostics-v2/reset-after-client.png').convert('RGB'));assert float(client.std())>15
            report['clientCaptureValid']=True;report['passed']=True
        finally:p.call('stateload','user',False);report['userStateRestored']=True
except Exception as e:report.update(passed=False,error=str(e));raise
finally:
    try:
        subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    finally:
        report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];exit_path=ROOT/f'diagnostics-v2/game-exit-{pid}.json';report['exit']=json.loads(exit_path.read_text()) if exit_path.exists() else None
        report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit'] and report['exit']['exitCode']=='0x0'
        (ROOT/f'diagnostics-v2/device-reset-{pid}-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
