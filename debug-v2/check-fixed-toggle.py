"""Cold-test the reversible fixed-room decoration setting, preserving user files."""
from debug_config import debug_root
import json,os,pathlib,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify
tmp=debug_root();config=EXE.parent/'AriaWide.ini'
assert not config.exists(),'This test only creates an absent temporary config; preserve existing user configuration.'
report=[]
def command(name,*args):subprocess.run([sys.executable,str(ROOT/'debug-v2'/name),*args],check=True,timeout=100)
def sample(enabled):
    with Probe() as p:
        p.call('statesave','original')
        try:
            p.call('stateimport','boss',str(tmp/'chaos-boss').replace('\\','/'));p.call('stateload','boss');time.sleep(.2)
            label=f'fixed-toggle-{int(enabled)}';meta=p.capture(label,True,at_present=True)
            image=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
            sides=[int(np.count_nonzero(image[1:161,:24])),int(np.count_nonzero(image[1:161,264:]))]
            assert meta['viewport']['expanded']==enabled,(meta,sides)
            assert (min(sides)>1000 if enabled else max(sides)==0),(enabled,sides)
            p.call('stateimport','edge',str(tmp/'user-slot3-right-edge').replace('\\','/'));p.call('stateload','edge');time.sleep(.15)
            edge=p.capture(f'fixed-toggle-{int(enabled)}-large',False,at_present=True)
            assert edge['viewport']['left']==48 and edge['viewport']['expanded'],edge
            report.append({'enabled':enabled,'fixedSidePixels':sides,'largeRoomViewport':edge['viewport']})
        finally:p.call('stateload','original')
sample(True)
pid=identify();command('close-system-command.py');assert json.loads((ROOT/f'diagnostics-v2/system-close-{pid}.json').read_text())['exitCode']=='0x0'
try:
    config.write_text('[AriaWide]\nExtendFixedRooms=0\n',encoding='ascii')
    command('quiet-game.py','--launch','--seconds','8');command('start-fixture.py','--slot','3');sample(False)
    pid=identify();command('close-system-command.py');assert json.loads((ROOT/f'diagnostics-v2/system-close-{pid}.json').read_text())['exitCode']=='0x0'
finally:
    if config.exists():config.unlink()
command('quiet-game.py','--launch','--seconds','8');command('start-fixture.py','--slot','3');sample(True)
(ROOT/'diagnostics-v2/fixed-toggle-check.json').write_text(json.dumps({'passed':True,'samples':report},indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'samples':report}),flush=True)
