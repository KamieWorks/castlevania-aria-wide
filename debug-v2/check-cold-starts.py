"""Cold-start the installed proxy, use slot three's real doorway, then close.

No diagnostic lifetime fix is injected. Window/input guards are debug-only.
"""
import argparse,json,subprocess,sys,time,ctypes
import numpy as np
from ctypes import wintypes as W
from harness import Probe,ROOT,identify
parser=argparse.ArgumentParser();parser.add_argument('--runs',type=int,default=3);args=parser.parse_args()
report=[]
def command(name,*args):
    subprocess.run([sys.executable,str(ROOT/'debug-v2'/name),*args],check=True,timeout=100)
for run in range(args.runs):
    command('quiet-game.py','--launch','--seconds','8')
    quiet=json.loads((ROOT/'diagnostics-v2/quiet-game-check.json').read_text())
    assert quiet['pid']==quiet['launcher']['pid'] and not quiet['gameForegroundObserved'],quiet
    assert quiet['audioSessions'] and all(s['muted'] for s in quiet['audioSessions']),quiet
    command('start-fixture.py','--slot','3')
    with Probe() as p:
        source=p.capture(f'cold-{run}-save',True,at_present=True)
        assert [source['area'],source['room'],source['playState']]==[0,36,1],source
        p.call('pulse',[203],1500);time.sleep(.3)
        edge=p.capture(f'cold-{run}-edge',True,at_present=True)
        assert [edge['area'],edge['room'],edge['cameraX'],edge['viewport']['left']]==[0,5,272,48],edge
        raw=(ROOT/f'private-v2/captures/cold-{run}-edge.ppu').read_bytes();i=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
        native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+i*0x14000).reshape(160,256)[:,:240]
        output=np.fromfile(ROOT/f'private-v2/captures/cold-{run}-edge.rgb555',dtype='<u2').reshape(162,288)
        assert np.array_equal(native,output[1:161,48:288]),'Native raster mismatch'
        stats=p.call('stats');assert stats['module']=='d3d9.dll',stats
        pid=p.pid
    command('close-system-command.py')
    closed=json.loads((ROOT/f'diagnostics-v2/system-close-{pid}.json').read_text());assert closed['exitCode']=='0x0',closed
    row={'run':run,'pid':pid,'quiet':quiet,'nativeCenterEqual':True,'rightEdgeViewport':edge['viewport'],'exitCode':closed['exitCode']}
    report.append(row);(ROOT/'diagnostics-v2/cold-starts-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'run':run,'pid':pid,'passed':True,'exitCode':closed['exitCode']}),flush=True)
