"""Native GBA map/menu and collection pause/resume without saving slots."""
from debug_config import debug_root
import json,os,pathlib,time,runpy,subprocess,sys,shutil
from harness import Probe,ROOT
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
tmp=debug_root()
report=[]
with Probe() as p:
    p.call('stateimport','fixture',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','fixture')
    for name,key in [('gba-start',28),('gba-map',15)]:
        p.call('pulse',[key],100);time.sleep(.5);p.capture(name,True,at_present=True)
        meta=json.loads((ROOT/'diagnostics-v2'/f'{name}.json').read_text())
        report.append({k:meta[k] for k in ['gameMode','playState','width','height']})
        p.call('pulse',[key],100);time.sleep(.5)
    p.call('uipulse',[59],100,state['hwnd'])
    subprocess.run([sys.executable,str(ROOT/'debug-v2/backbuffer-shot.py'),'collection-pause-current'],check=True,timeout=18)
    # F1 toggles collection pause. A may select a remembered row, so don't use it.
    p.call('uipulse',[59],100,state['hwnd']);time.sleep(.2)
    p.capture('menus-resumed',True)
    meta=json.loads((ROOT/'diagnostics-v2/menus-resumed.json').read_text())
    assert meta['gameMode']==4 and meta['playState']==1,meta
    report.append({'resumed':True,'stats':p.call('stats')})
(ROOT/'diagnostics-v2/menu-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
