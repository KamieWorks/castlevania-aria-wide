"""Verify the diagnostic cloud-write guard on normal exit, preserving real files."""
from debug_config import debug_root, profile_root
import hashlib,json,os,pathlib,subprocess,sys,time,runpy
from harness import identify,ROOT,Probe
pid=identify();directory=debug_root()/f'cloud-isolation-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
before=hashes();log=ROOT/'diagnostics-v2/cloud-isolation-errors.log'
child=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(log,'a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(child.stdout.readline());assert ready['ready'],ready
window=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
with Probe() as p:
    # Exercise the collection's real last-played/settings write path, without
    # writing a GBA save slot: exit to game cards, then select Aria again.
    for keys in [[59],[203],[44],[44],[44]]:
        p.call('uipulse',keys,100,window['hwnd']);time.sleep(.4)
    time.sleep(5)
# Guard stays attached through the actual process exit; no loaded old fixture
# can flush to the user's persistent data during diagnostic cleanup.
subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],check=True,timeout=30)
child.wait(timeout=15);time.sleep(.5);after=hashes()
events=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
closed=json.loads((ROOT/f'diagnostics-v2/system-close-{pid}.json').read_text())
report={'pid':pid,'before':before,'after':after,'events':events,'exitCode':closed['exitCode']}
report['passed']=before==after and closed['exitCode']=='0x0' and any(e.get('type')=='FileWrite' for e in events) and not any(e.get('type') in ['FileWriteAsync','FileWriteStreamOpen','FileWriteStreamWriteChunk'] or 'error' in e for e in events)
(ROOT/'diagnostics-v2/cloud-isolation-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True);assert report['passed'],report
