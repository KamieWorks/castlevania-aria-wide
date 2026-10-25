"""Enter the final-boss scene from a private copy of the existing Soma fixture."""
from debug_config import debug_root
import os,pathlib,json,time,shutil
from harness import Probe,ROOT
tmp=debug_root()
report={}
with Probe() as p:
    p.call('stateimport','soma',str(tmp/'soma-chaos-save').replace('\\','/'));p.call('stateload','soma')
    # This fixture was taken in the native main menu. B closes it; START does
    # not, so gate on playState rather than assuming a key toggles a menu.
    p.call('pulse',[45],100);time.sleep(.7)
    p.capture('chaos-source',True)
    source=json.loads((ROOT/'diagnostics-v2/chaos-source.json').read_text());assert source['playState']==1,source
    p.call('statesave','safe',str(tmp/'soma-safe-room').replace('\\','/'))
    for ext in ('json','bin'):shutil.copy2(tmp/('soma-safe-room.state.'+ext),ROOT/'private-v2/states'/('soma-safe-room.state.'+ext))
    raw=(ROOT/'private-v2/captures/chaos-source.ewram').read_bytes()
    assert int.from_bytes(raw[0x88:0x8c],'little')==0x084f92a4
    report['door']=p.call('debugdoor',0,0x084f93bc)
    p.call('debugentry',0x084f93bc,120,175)
    report['position']=p.call('debugposition',8,191)
    p.call('pulse',[203],550);time.sleep(1)
    report['restoredDoor']=p.call('restoredoors')
    report['entryPlacement']=p.call('debugentryresult')
    p.capture('chaos-boss-entry',True)
    raw=(ROOT/'private-v2/captures/chaos-boss-entry.ewram').read_bytes()
    report['roomPointer']=hex(int.from_bytes(raw[0x88:0x8c],'little'))
    assert report['roomPointer']=='0x84f93bc',report
    report['state']={k:v for k,v in p.call('statesave','boss',str(tmp/'chaos-boss').replace('\\','/')).items() if k!='tags'}
    for ext in ('json','bin'):shutil.copy2(tmp/('chaos-boss.state.'+ext),ROOT/'private-v2/states'/('chaos-boss.state.'+ext))
    for keys,ms in [([203],550),([45],350),([44],120),([45],350)]:p.call('pulse',keys,ms)
    time.sleep(.4);p.capture('chaos-boss-action',True)
    report['status']=p.call('status');report['stats']=p.call('stats')
    # Return to the original safe room, keeping the combat snapshot private.
    p.call('stateload','safe');p.capture('chaos-restored-save',True)
(ROOT/'diagnostics-v2/chaos-boss-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
