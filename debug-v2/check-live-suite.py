"""Serial cold-DLL regressions, with profile writes isolated through exit."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,subprocess,sys,time
from harness import Probe,ROOT,EXE,identify
parser=argparse.ArgumentParser();parser.add_argument('--version',choices=['v19','v20'],default='v20');args=parser.parse_args();version=args.version
pid=identify();tmp=debug_root();directory=tmp/f'live-suite-{pid}';prefix=str(tmp/'live-suite-user').replace('\\','/')
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'tests':[]};saved=False
latest_report=ROOT/f'diagnostics-v2/live-suite-{version}-check.json'
if latest_report.exists():
    previous=json.loads(latest_report.read_text());history=ROOT/f'diagnostics-v2/live-suite-{version}-{previous["pid"]}-check.json'
    if not history.exists():history.write_bytes(latest_report.read_bytes())
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/live-suite-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user',prefix);saved=True
        p.call('pulse',[203],1500);m=p.capture(f'user-edge-client-source-{version}',True,at_present=True)
        assert [m['area'],m['room'],m['viewport']['left']]==[0,5,48],m
    subprocess.run([sys.executable,str(ROOT/'debug-v2/backbuffer-shot.py'),f'user-edge-client-{version}'],check=True,timeout=18)
    required=[('check-edge-framing.py',[]),('check-fixed-cold.py',['--version',version]),('check-edge-objects.py',[]),('check-blends.py',[]),('check-affine.py',[]),('check-affine-rooms.py',[]),('check-rewind.py',[]),('check-menus.py',[])]
    if version=='v20':required.insert(1,('check-unused-oam.py',[]))
    for script,script_args in required:
        start=time.monotonic();r=subprocess.run([sys.executable,str(ROOT/'debug-v2'/script),*script_args],timeout=85)
        row={'script':script,'exitCode':r.returncode,'seconds':time.monotonic()-start};report['tests'].append(row);print(json.dumps(row),flush=True)
        if r.returncode:raise RuntimeError(f'{script} failed')
finally:
    try:
        if saved:
            with Probe() as p:p.call('stateimport','user',prefix);p.call('stateload','user',False)
    finally:
        subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
        report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
        report['passed']=len(report['tests'])==len(required) and all(t['exitCode']==0 for t in report['tests']) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0'
        (ROOT/f'diagnostics-v2/live-suite-{version}-{pid}-check.json').write_text(json.dumps(report,indent=2));latest_report.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
assert report['passed'],report
