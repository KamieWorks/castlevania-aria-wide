"""From verified area 0/room 35 entrance, follow its upper left door to room 10."""
from debug_config import debug_root
import time,os,pathlib,json,shutil
from harness import Probe,ROOT
tmp=debug_root()
with Probe() as p:
    p.capture('door-before',True)
    meta=json.loads((ROOT/'diagnostics-v2/door-before.json').read_text())
    if (meta['area'],meta['room'],meta['playState'])!=(0,35,1):raise RuntimeError('Expected verified entrance fixture')
    print(p.call('debugposition',40,144),flush=True)
    p.call('pulse',[203],650);time.sleep(.7);p.capture('door-after',True)
    meta=json.loads((ROOT/'diagnostics-v2/door-after.json').read_text())
    if (meta['area'],meta['room'])!=(0,10):raise RuntimeError('Expected room 10 after legal doorway')
    for key,ms in [(203,2000),(203,1500),(205,1200)]:p.call('pulse',[key],ms)
    p.capture('wide-v7-fixture',True)
    r=p.call('statesave','wide',str(tmp/'wide-room10').replace('\\','/'));print({k:v for k,v in r.items() if k!='tags'})
    for ext in ('json','bin'):shutil.copy2(tmp/('wide-room10.state.'+ext),ROOT/'private-v2/states'/('wide-room10.state.'+ext))
