"""Use the collection's actual Shift+Left rewind shortcut, without global input."""
from debug_config import debug_root
import json,os,pathlib,time,runpy
from harness import Probe,ROOT
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
tmp=debug_root()
report={}
with Probe() as p:
    p.call('stateimport','fixture',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','fixture')
    p.call('statewatch')
    # Populate actual M2 history with this room, rather than rewinding into
    # unrelated diagnostic fixtures recorded before the test began.
    time.sleep(20)
    p.capture('rewind-start',True)
    p.call('pulse',[205],2000);time.sleep(.3);p.capture('rewind-forward',True)
    report['input']=p.call('uipulse',[42,203],800,state['hwnd'])
    time.sleep(.3);p.capture('rewind-after',True)
    report['nativeStateCalls']=p.call('statecounts')
    assert report['nativeStateCalls']['loads']>0,report
    for label in ['start','forward','after']:
        meta=json.loads((ROOT/'diagnostics-v2'/f'rewind-{label}.json').read_text())
        report[label]={k:meta[k] for k in ['area','room','playState','cameraX','cameraY','playerX','playerY']}
        report[label]['viewport']=meta.get('viewport')
    assert [report['after']['area'],report['after']['room'],report['after']['playState']]==[0,10,1],report
    assert report['after']['cameraX']<report['forward']['cameraX'],report
    report['passed']=True
(ROOT/'diagnostics-v2/rewind-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
