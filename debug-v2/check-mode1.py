"""Use the game's transition handler to enter an affine-mode room for rendering QA.

Only the private runtime ROM copy's one door destination is temporarily changed.
It is restored before capture and again on bridge cleanup if anything fails.
"""
from debug_config import debug_root
import os,pathlib,json,time,shutil
from harness import Probe,ROOT
tmp=debug_root()
report={}
with Probe() as p:
    p.capture('soma-fixture-before',True)
    p.call('statesave','soma',str(tmp/'soma-chaos-save').replace('\\','/'))
    for ext in ('json','bin'):shutil.copy2(tmp/('soma-chaos-save.state.'+ext),ROOT/'private-v2/states'/('soma-chaos-save.state.'+ext))
    report['replacement']=p.call('hotreplace',str(tmp/'realtime-v9.dll').replace('\\','/'))
    p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','wide')
    report['door']=p.call('debugdoor',1,0x084ec3f0)
    p.capture('mode1-before-transition',True)
    report['position']=p.call('debugposition',495,191)
    p.call('pulse',[205],850);time.sleep(1.5)
    report['restoration']=p.call('restoredoors')
    p.capture('mode1-room',True,at_present=True)
    raw=(ROOT/'private-v2/captures/mode1-room.ewram').read_bytes()
    room=int.from_bytes(raw[0x88:0x8c],'little');report['roomPointer']=hex(room)
    assert room==0x084ec3f0,report
    meta=json.loads((ROOT/'diagnostics-v2/mode1-room.json').read_text());report['metadata']=meta
    assert meta['dispcnt']&7==1,report
    r=p.call('statesave','mode1',str(tmp/'mode1-room').replace('\\','/'));report['state']={k:v for k,v in r.items() if k!='tags'}
    for ext in ('json','bin'):shutil.copy2(tmp/('mode1-room.state.'+ext),ROOT/'private-v2/states'/('mode1-room.state.'+ext))
    report['passed']=True
(ROOT/'diagnostics-v2/mode1-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='metadata'}),flush=True)
