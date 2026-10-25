"""Collection-menu input through process-local DirectInput, with temporary focus-query override."""
import argparse,runpy
from harness import Probe,ROOT,KEYS
p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('--ms',type=int,default=160);a=p.parse_args()
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
with Probe() as probe:print(probe.call('uipulse',[KEYS[k] for k in a.key.split('+')],a.ms,state['hwnd']))
