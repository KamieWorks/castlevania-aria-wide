"""Round-trip the emulator's own state in memory, never a user's save slot."""
from debug_config import debug_root
import json,os,pathlib,time,shutil
from harness import Probe,ROOT,KEYS
temp=debug_root()
private=ROOT/'private-v2/states';private.mkdir(exist_ok=True)
report={}
with Probe() as p:
    p.capture('state-before',True)
    report['saved']=p.call('statesave','roundtrip',str(temp/'julius-save-room').replace('\\','/'))
    print(json.dumps(report['saved']),flush=True)
    for ext in ('bin','json'):shutil.copy2(temp/('julius-save-room.state.'+ext),private/('julius-save-room.state.'+ext))
    p.call('pulse',[KEYS['left']],550);p.capture('state-moved',True)
    report['loaded']=p.call('stateload','roundtrip')
    assert all(report['saved'][k]==report['loaded'][k] for k in ('room','x','y')),report
    p.capture('state-restored',True)
    report['stats']=p.call('stats');report['passed']=True
(ROOT/'diagnostics-v2/state-roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
