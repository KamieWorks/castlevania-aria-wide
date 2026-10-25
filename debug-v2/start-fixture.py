"""Load an existing slot via verified menu stages. Never copy, delete or save."""
import time,runpy,json,argparse,sys
from harness import identify,Probe,ROOT
parser=argparse.ArgumentParser();parser.add_argument('--slot',type=int,choices=[1,2,3],default=2);parser.add_argument('--title-only',action='store_true');parser.add_argument('--main-menu-only',action='store_true');args=parser.parse_args()
start=time.monotonic()
while True:
    try:identify();break
    except RuntimeError:
        if time.monotonic()-start>25:raise
        time.sleep(.25)
while True:
    try:state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'));break
    except RuntimeError as e:
        if 'Ambiguous visible game windows: []' not in str(e) or time.monotonic()-start>25:raise
        time.sleep(.25)
def wait(probe,predicate,seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        status=probe.call('status')
        if predicate(status):return status
        time.sleep(.1)
    raise RuntimeError(f'Menu gate timeout: {status}')
with Probe() as p:
    # Steam startup may still be loading collection/title assets. Continue
    # bounded confirmations only until the first actual GBA frame is observed.
    for _ in range(6):
        if p.call('status')['context']:break
        print(p.call('uipulse',[44],100,state['hwnd']),flush=True)
        time.sleep(1.5)
    wait(p,lambda s:s['context'] is not None)
    # Logos and the opening may be playing; use START only to reach the stable title gate.
    end=time.monotonic()+20
    while True:
        s=p.call('status')
        if s['gameMode']==1 and s['stage']==8:break
        if s['gameMode'] in [0,7]:p.call('pulse',[28],100)
        if time.monotonic()>end:raise RuntimeError(f'Title gate timeout: {s}')
        time.sleep(.15)
    if args.title_only:
        p.capture('fixture-title',True);sys.exit(0)
    p.call('pulse',[44],100)
    wait(p,lambda s:s['gameMode']==2 and s['stage']==3)
    if args.main_menu_only:
        p.capture('fixture-main-menu',True);sys.exit(0)
    p.call('pulse',[44],100)
    wait(p,lambda s:s['gameMode']==2 and s['stage']==6)
    p.capture('fixture-list',True)
    for _ in range(args.slot-1):p.call('pulse',[205],100);time.sleep(.3)
    p.capture(f'fixture-slot{args.slot}',True)
    p.call('pulse',[44],100)
    wait(p,lambda s:s['gameMode']==4,10);time.sleep(1)
    p.capture('fixture-loaded',True)
