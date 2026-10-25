"""Use collection restart menu, without any save/overwrite action."""
import runpy,time,subprocess,sys
from harness import Probe,ROOT
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
with Probe() as p:
    for key in [59,200,203,44,44]:
        print(p.call('uipulse',[key],100,state['hwnd']),flush=True)
    time.sleep(.5)
    print(p.call('status'))
