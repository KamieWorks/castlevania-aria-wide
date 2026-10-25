"""Repeatable wide-room state/history compatibility checks."""
from debug_config import debug_root
import os,pathlib,shutil,json,time
import numpy as np
from harness import Probe,ROOT
tmp=debug_root()
prefix=str(tmp/'wide-room10').replace('\\','/')
for ext in ('json','bin'):shutil.copy2(ROOT/'private-v2/states'/('wide-room10.state.'+ext),tmp/('wide-room10.state.'+ext))
report={}
with Probe() as p:
    report['replacement']=p.call('hotreplace',str(tmp/'realtime-v8.dll').replace('\\','/'))
    report['import']=p.call('stateimport','legacy',prefix)
    p.call('stateload','legacy');time.sleep(.1);p.capture('v8-legacy-loaded',True)
    report['saved']=p.call('statesave','with-margins',str(tmp/'v8-wide').replace('\\','/'))
    assert 'ARIA-WIDE-1' in report['saved']['tags']
    report['saved'].pop('tags')
    p.call('pulse',[205],900);p.capture('v8-state-moved',True)
    report['loaded']=p.call('stateload','with-margins');p.capture('v8-state-restored',True)
    assert all(report['saved'][k]==report['loaded'][k] for k in ('room','x','y'))
    # Pixel-exact preservation of the original center in non-blended mode.
    raw=(ROOT/'private-v2/captures/v8-state-restored.ppu').read_bytes()
    mode=int.from_bytes(raw[0x2205c:0x22060],'little')
    assert mode==0,mode
    frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
    center=np.frombuffer(raw,dtype='<u2',count=256*160,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
    output=np.fromfile(ROOT/'private-v2/captures/v8-state-restored.rgb555',dtype='<u2').reshape(162,288)
    report['centerEqual']=bool(np.array_equal(center,output[1:161,24:264]));assert report['centerEqual']
    report['stats']=p.call('stats');report['passed']=True
    for ext in ('json','bin'):shutil.copy2(tmp/('v8-wide.state.'+ext),ROOT/'private-v2/states'/('v8-wide.state.'+ext))
(ROOT/'diagnostics-v2/wide-state-roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
