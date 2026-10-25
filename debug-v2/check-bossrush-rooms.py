"""Native Boss Rush room/action rendering coverage; does not claim boss clears.

Private RAM/door fixtures stay outside the player DLL and distribution. The
native 1P chain is reported separately from the retail debug-only second chain.
Run on a fresh quiet-game.py launch, with no other controlling test running.
"""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,shutil,subprocess,sys,time
import numpy as np
from harness import Probe,ROOT,EXE,identify

pid=identify();tmp=debug_root()
graph={r['pointer']:r for r in json.loads((ROOT/'private-v2/room-graph.json').read_text())}
def component(root):
    seen=set();queue=[root]
    while queue:
        p=queue.pop()
        if p in seen:continue
        seen.add(p);queue.extend(d['destination'] for d in graph[p]['doors'])
    return seen
native=component(0x084fb0b4);debug=component(0x084fa920)
assert len(native)==len(debug)==12 and native.isdisjoint(debug)
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'coverage':'Native doorway/action/raster coverage, not complete boss fights. Second chain is retail debug-only.',
        'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'rooms':[]}
out=ROOT/f'diagnostics-v2/bossrush-rooms-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2),encoding='utf-8')
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'bossrush-rooms-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/bossrush-rooms-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected'],ready
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','3'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user');p.call('stateimport','source',str(tmp/'native-bossrush-start').replace('\\','/'))
        def capture(label,target):
            meta=p.capture(label,True,at_present=True);prefix=ROOT/f'private-v2/captures/{label}'
            ram=prefix.with_suffix('.ewram').read_bytes();raw=prefix.with_suffix('.ppu').read_bytes()
            header=int.from_bytes(ram[0x88:0x8c],'little');view=meta['viewport']
            assert header==target['pointer'] and meta['playState']==1,(hex(header),meta)
            assert view['expanded'] and view['width']==(240 if target['width']==1 else target['width']*256),view
            assert meta['dispcnt']&7==target['mode'],meta
            assert int.from_bytes(ram[0x4cc:0x4d0],'little')&1,'Native Boss Rush flag was lost'
            blend=int.from_bytes(raw[0x2205c:0x22060],'little');assert blend==0,blend
            frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
            center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
            output=np.fromfile(prefix.with_suffix('.rgb555'),dtype='<u2').reshape(162,288);left=view['left']
            assert np.array_equal(center,output[1:161,left:left+240]),'Original raster differs'
            entities=[hex(int.from_bytes(ram[0x4e4+i*0x84:0x4e8+i*0x84],'little')) for i in range(224) if int.from_bytes(ram[0x4e4+i*0x84:0x4e8+i*0x84],'little')]
            return {'label':label,'centerEqual':True,'viewport':view,'hardwareMode':meta['dispcnt']&7,
                    'hp':int.from_bytes(ram[0x1326e:0x13270],'little'),'frameHash':meta['frame_sha256'],
                    'entityCount':len(entities),'entityUpdates':sorted(set(entities)),
                    'sideNonzero':[int(np.count_nonzero(output[1:161,:left])),int(np.count_nonzero(output[1:161,left+240:]))]}
        try:
            for pointer in sorted(native)+sorted(debug):
                target=graph[pointer];row={'header':hex(pointer),'chain':'native-1P' if pointer in native else 'retail-debug-second','size':[target['width'],target['height']],'samples':[]}
                try:
                    p.call('stateload','source')
                    if pointer!=0x084fb0b4:
                        p.call('debugdoor',0,pointer);p.call('debugentry',pointer,120,120 if target['height']==1 else 352)
                        p.call('pulse',[205],1600);deadline=time.monotonic()+10
                        while True:
                            meta=p.capture('bossrush-transition',True,at_present=True);ram=(ROOT/'private-v2/captures/bossrush-transition.ewram').read_bytes()
                            if int.from_bytes(ram[0x88:0x8c],'little')==pointer and meta['playState']==1:break
                            if time.monotonic()>deadline:raise RuntimeError('Native doorway did not settle')
                            time.sleep(.2)
                        p.call('restoredoors')
                    time.sleep(.4)
                    label=f'bossrush-room-{pointer:08x}';row['samples'].append(capture(label+'-entry',target))
                    p.call('statesave',label,str(tmp/label).replace('\\','/'))
                    for ext in ('json','bin'):shutil.copy2(tmp/(label+'.state.'+ext),ROOT/'private-v2/states'/(label+'.state.'+ext))
                    p.call('pulse',[44,45],500);time.sleep(.4);row['samples'].append(capture(label+'-action',target))
                    time.sleep(.8);row['samples'].append(capture(label+'-recovery',target));row['passed']=True
                except Exception as e:row.update(passed=False,error=str(e))
                finally:p.call('restoredoors')
                report['rooms'].append(row);save();print(json.dumps({'header':row['header'],'chain':row['chain'],'passed':row['passed'],'error':row.get('error')}),flush=True)
        finally:p.call('restoredoors');p.call('stateload','user',False);report['userStateRestored']=True
    report['passed']=len(report['rooms'])==24 and all(r['passed'] for r in report['rooms'])
except Exception as e:report.update(passed=False,error=str(e));raise
finally:
    try:
        try:alive=identify()==pid
        except RuntimeError as e:
            if 'found []' not in str(e):raise
            alive=False
        if alive:subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30)
        guard.wait(timeout=15);report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after']
        exit_path=ROOT/f'diagnostics-v2/game-exit-{pid}.json';report['exit']=json.loads(exit_path.read_text()) if exit_path.exists() else None
        report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit'] and report['exit']['exitCode']=='0x0'
    finally:save();print(json.dumps({'pid':pid,'passed':report.get('passed'),'exit':report.get('exit')}),flush=True)
