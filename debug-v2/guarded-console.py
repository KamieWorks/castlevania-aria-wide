"""Single process-local controller for gated UI diagnostics; no desktop input."""
from debug_config import debug_root, profile_root
import argparse,hashlib,json,os,pathlib,runpy,subprocess,sys,time
from harness import Probe,ROOT,EXE,identify,KEYS
ap=argparse.ArgumentParser();ap.add_argument('--slot',type=int,choices=[1,2,3],default=3);args=ap.parse_args()
pid=identify();directory=debug_root()/f'console-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'before':hashes(),'commands':[]}
report_path=ROOT/f'diagnostics-v2/console-{pid}-check.json'
def save_report():report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
save_report()
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/console-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot',str(args.slot)],check=True,timeout=100)
    window=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
    with Probe() as p:
        print(json.dumps({'ready':True,'pid':pid,'lifecycle':p.call('lifecycle')}),flush=True)
        for line in sys.stdin:
            command=json.loads(line);command['time']=time.time();report['commands'].append(command);save_report()
            if command.get('close'):break
            try:
                if 'ui' in command:
                    result=p.call('uipulse',[KEYS[k] for k in command['ui'].split('+')],command.get('ms',100),window['hwnd']);time.sleep(.6)
                elif 'pulse' in command:result=p.call('pulse',[KEYS[k] for k in command['pulse'].split('+')],command.get('ms',100))
                elif 'rpc' in command:result=p.call(command['rpc'],*command.get('args',[]))
                elif 'shot' in command:
                    subprocess.run([sys.executable,str(ROOT/'debug-v2/backbuffer-shot.py'),command['shot']],check=True,timeout=18);result={'shot':command['shot']}
                elif 'gba' in command:result=p.capture(command['gba'],True,at_present=True)
                elif 'wait' in command:time.sleep(min(10,command['wait']));result={'waited':True}
                else:result={'rom':p.call('romcode'),'status':p.call('status'),'lifecycle':p.call('lifecycle')}
                command['result']=result;print(json.dumps({'result':result}),flush=True)
            except Exception as e:command['error']=str(e);print(json.dumps({'error':str(e)}),flush=True)
            finally:save_report()
finally:
    try:
        try:alive=identify()==pid
        except RuntimeError as e:
            if 'found []' not in str(e):raise
            alive=False
        if alive:subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30)
        else:report['gameAlreadyExited']=True
        guard.wait(timeout=15)
    except Exception as e:report['cleanupError']=str(e);raise
    finally:
        report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after']
        exit_path=ROOT/f'diagnostics-v2/game-exit-{pid}.json';report['exit']=json.loads(exit_path.read_text()) if exit_path.exists() else None
        save_report();print(json.dumps({'realSavesUnchanged':report['realSavesUnchanged'],'exit':report['exit']}),flush=True)
