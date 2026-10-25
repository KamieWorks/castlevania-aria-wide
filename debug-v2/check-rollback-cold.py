"""Verify the actual checkpoint DLL after restarting Steam's game process."""
from debug_config import debug_root
import json,os,pathlib,hashlib,time
import numpy as np
from harness import Probe,ROOT,EXE
tmp=debug_root();report={}
expected=hashlib.sha256((ROOT/'patch-checkpoints/v10/d3d9.dll').read_bytes()).hexdigest()
report['sha256']=hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest();assert report['sha256']==expected
with Probe() as p:
    report['stats']=p.call('stats');assert report['stats']['module']=='d3d9.dll'
    for name in ['chaos-boss','v8-wide','julius-save-room']:p.call('stateimport',name,str(tmp/name).replace('\\','/'))
    for name,label in [('chaos-boss','rollback-cold-boss'),('v8-wide','rollback-cold-wide')]:
        p.call('stateload',name);time.sleep(.15);meta=p.capture(label,True,at_present=True)
        out=np.fromfile(ROOT/'private-v2/captures'/f'{label}.rgb555',dtype='<u2').reshape(162,288)
        report[label]=[int(np.count_nonzero(out[1:161,:24])),int(np.count_nonzero(out[1:161,264:]))]
    assert report['rollback-cold-boss']==[0,0],report
    assert all(n>100 for n in report['rollback-cold-wide']),report
    p.call('stateload','julius-save-room');report['passed']=True
(ROOT/'diagnostics-v2/rollback-cold-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
