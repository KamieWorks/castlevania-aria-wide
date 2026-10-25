"""Fault-inject before enable; check original code and restart the active patch."""
from debug_config import debug_root
import json,os,pathlib
from harness import Probe,ROOT
tmp=debug_root();report=[]
with Probe() as p:
    for stage in (1,2,3):
        result=p.call('initfailuretest',str(tmp/f'init-failure-v16-{stage}.dll').replace('\\','/'))
        assert result=={'result':-100-stage,'originalCodeUnchanged':True,'reinstalled':0},result
        p.capture(f'init-failure-{stage}-resumed',True);report.append(result)
    report.append(p.call('lifecycle'))
(ROOT/'diagnostics-v2/init-failure-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
