"""Record the user's slot-three room; only private native-memory fixtures are written."""
from debug_config import debug_root
import os,pathlib,json,shutil,time
from harness import Probe,ROOT
tmp=debug_root()
with Probe() as p:
    meta=p.capture('user-edge-before',True,at_present=True)
    assert (meta['area'],meta['room'],meta['playState'])==(0,5,1),meta
    saved=p.call('statesave','edge',str(tmp/'user-slot3-right-edge').replace('\\','/'))
    for ext in ['json','bin']:shutil.copy2(tmp/f'user-slot3-right-edge.state.{ext}',ROOT/f'private-v2/states/user-slot3-right-edge.state.{ext}')
    print({k:v for k,v in saved.items() if k!='tags'})
