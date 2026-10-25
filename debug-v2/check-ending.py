"""Replay a retail event driver in private state with Steam writes isolated."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,subprocess,sys,time,runpy
from harness import Probe,ROOT,identify
parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['bad','true','julius','chaos'],default='true');parser.add_argument('--seconds',type=int,default=60);parser.add_argument('--require-credits',action='store_true');parser.add_argument('--native-chaos',action='store_true');parser.add_argument('--native-request',action='store_true');parser.add_argument('--finish-credits',action='store_true');args=parser.parse_args()
if args.native_chaos:assert args.kind=='chaos'
if args.native_request:assert args.kind!='chaos'
pid=identify();tmp=debug_root();directory=tmp/f'ending-{args.kind}-{pid}'
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
before=hashes();report={'kind':args.kind,'pid':pid,'before':before,'samples':[]}
child=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(directory).replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/ending-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
guard=json.loads(child.stdout.readline());assert guard['ready'] and guard['achievementsProtected'],guard
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),*(['--slot','3'] if args.native_chaos or args.native_request else ['--main-menu-only'])],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user')
        try:
            # A fresh process stopped at the GBA title supplies the clean
            # globals expected by the original retail event-test driver.
            if args.native_chaos or args.native_request:
                p.call('stateimport','soma',str(tmp/'soma-safe-room').replace('\\','/'));p.call('stateload','soma')
            report['driver']=p.call('nativechaosending') if args.native_chaos else p.call('nativeendingrequest',args.kind) if args.native_request else p.call('debugending',args.kind);start=time.monotonic();index=0
            while time.monotonic()-start<args.seconds:
                time.sleep(1.5);label=f'ending-{args.kind}-{index}';meta=p.capture(label,True,at_present=True)
                row={'label':label,'elapsed':time.monotonic()-start,'frameHash':meta['frame_sha256'],'mode':meta['gameMode'],'playState':meta['playState'],'viewport':meta['viewport'],'event':p.call('endingstatus')}
                assert [meta['width'],meta['height']]==[288,162],meta
                report['samples'].append(row);print(json.dumps(row),flush=True);index+=1
                credits=sum(r['mode']==6 for r in report['samples'])>=3
                if credits and (meta['gameMode'] in [0,1] if args.finish_credits else meta['gameMode']==6):break
                p.call('pulse',[44],100)
            report['continuedFrames']=len({r['frameHash'] for r in report['samples']})>1
            report['requestedHeaderSeen']=any(r['event']['roomPointer']==report['driver']['targetHeader'] for r in report['samples'])
            report['completedEnding']=sum(r['mode']==6 for r in report['samples'])>=3
            report['creditsFinished']=report['completedEnding'] and report['samples'][-1]['mode'] in [0,1]
            report['coverage']='Private diagnostic entry through native scripted transition; ending and credits checkpoints are reported separately. No claim of a full gameplay playthrough.'
            report['finalPrivateState']={k:v for k,v in p.call('statesave','event-final',str(tmp/f'ending-{args.kind}-final').replace('\\','/')).items() if k!='tags'}
        finally:p.call('stateload','user',False)
finally:
    # Isolation remains attached through normal process exit, including host
    # cleanup/automatic writes. A failed event test must never flush to Steam.
    try:subprocess.run([sys.executable,str(ROOT/'debug-v2/close-system-command.py')],check=True,timeout=30)
    finally:child.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=before==report['after']
    report['cloudEvents']=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
    report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text()) if (ROOT/f'diagnostics-v2/game-exit-{pid}.json').exists() else None
    (ROOT/f'diagnostics-v2/ending-{args.kind}-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'kind':args.kind,'realSavesUnchanged':report['realSavesUnchanged'],'samples':len(report['samples']),'exit':report['exit']}),flush=True)
assert report['realSavesUnchanged'] and report.get('continuedFrames') and report.get('requestedHeaderSeen'),{'kind':args.kind,'realSavesUnchanged':report['realSavesUnchanged'],'continuedFrames':report.get('continuedFrames'),'requestedHeaderSeen':report.get('requestedHeaderSeen'),'report':f'ending-{args.kind}-check.json'}
if args.require_credits:assert report.get('completedEnding'),'Ending did not reach credits within the bounded test'
if args.finish_credits:assert report.get('creditsFinished'),'Credits did not finish within the bounded test'
