"""Capture allocation evidence while closing only the verified game's main window."""
from debug_config import debug_root
import json,os,pathlib,subprocess,sys,time,argparse
from harness import identify,ROOT
parser=argparse.ArgumentParser();parser.add_argument('--fix-movie-child',action='store_true');parser.add_argument('--fix-state-head',action='store_true');args=parser.parse_args()
pid=identify();tmp=debug_root();path=tmp/f'task-delete-{pid}.jsonl'
command=['node',str(ROOT/'debug-v2/task-delete-trace.mjs'),str(pid),str(path).replace('\\','/')]
if args.fix_movie_child:command.append('--fix-movie-child')
if args.fix_state_head:command.append('--fix-state-head')
child=subprocess.Popen(command,stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    if not json.loads(child.stdout.readline()).get('ready'):raise RuntimeError('Trace did not attach')
    subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],check=True,timeout=25)
    child.wait(timeout=15)
finally:
    if child.poll() is None:child.terminate();child.wait(timeout=5)
    if path.exists():(ROOT/'diagnostics-v2'/path.name).write_bytes(path.read_bytes())
if path.exists():
    rows=[json.loads(l) for l in path.read_text().splitlines()]
    print(json.dumps({'pid':pid,'events':len(rows),'last':rows[-8:]}))
