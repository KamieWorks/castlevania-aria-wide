"""Cold installation on the original JP depot or its separately backed-up translation."""
from debug_config import profile_root, debug_root
import argparse,hashlib,json,os,pathlib,struct,subprocess,sys,time
import numpy as np
from PIL import Image
from harness import Probe,ROOT,EXE,identify
ap=argparse.ArgumentParser();ap.add_argument('--variant',required=True,choices=['japanese','chinese']);ap.add_argument('--scratch',required=True);args=ap.parse_args();args.baseline=False
pid=identify();tmp=debug_root();version='v26';work=pathlib.Path(args.scratch).resolve()/(args.variant+'-'+str(pid));assert pathlib.Path(args.scratch).resolve().is_dir();work.mkdir()
remote=profile_root()
def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in remote.iterdir() if p.is_file()}
report={'pid':pid,'variant':args.variant,'noIni':not (EXE.parent/'AriaWide.ini').exists(),'baseline':args.baseline,'dllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'before':hashes(),'cases':[]}
out=ROOT/f'diagnostics-v2/install-{args.variant}-{pid}-check.json'
def save():out.write_text(json.dumps(report,indent=2))
guard=subprocess.Popen(['node',str(ROOT/'debug-v2/cloud-isolate.mjs'),str(pid),str(tmp/f'install-{args.variant}-{pid}').replace('\\','/')],stdout=subprocess.PIPE,stderr=open(ROOT/'diagnostics-v2/jitter-errors.log','a'),text=True,creationflags=subprocess.CREATE_NO_WINDOW)
ready=json.loads(guard.stdout.readline());assert ready['ready'] and ready['achievementsProtected']
try:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--title-only'],check=True,timeout=100)
    with Probe() as p:
        title=p.capture('install-'+args.variant+'-title',True,at_present=True)
        pixels=np.fromfile(tmp/('install-'+args.variant+'-title.rgb555'),dtype='<u2').reshape(162,288)
        assert not title['viewport']['expanded'] and not np.count_nonzero(pixels[:,:24]) and not np.count_nonzero(pixels[:,264:])
        rom=work/'running-rom.gba';info=p.call('romdump',str(rom).replace('\\','/'));assert info['code']=='A2CJ'
        report.update(romSHA256=hashlib.sha256(rom.read_bytes()).hexdigest(),romBytes=info['bytes'],titleCentered=True,title=title)
        rom.unlink();report['renderer']=p.call('stats');assert report['renderer']['module']=='d3d9.dll'
    subprocess.run([sys.executable,str(ROOT/'debug-v2/start-fixture.py'),'--slot','1'],check=True,timeout=100)
    with Probe() as p:
        p.call('statesave','user')
        try:
            initial=p.capture('install-'+args.variant+'-initial',True,at_present=True);report['initialRoom']=[initial['area'],initial['room']]
            if [initial['area'],initial['room']]!=[0,14]:
                query=p.call('roompointer',0,14);door=next(d for d in query['doors'] if d['x']==-1 and d['y']==0)
                try:
                    p.call('debugdoor',door['i'],query['target']);p.call('debugentry',query['target'],120,191)
                    p.call('debugposition',24,191);p.call('pulse',[203],650);time.sleep(.3)
                finally:p.call('restoredoors')
                report['diagnosticEntry']={'source':query['source'],'target':query['target'],'nativeDoorTransition':True,'diskRomUnchanged':True}
            fixed=p.capture('install-'+args.variant+'-fixed',True,at_present=True)
            pixels=np.fromfile(tmp/('install-'+args.variant+'-fixed.rgb555'),dtype='<u2').reshape(162,288)
            assert [fixed['area'],fixed['room']]==[0,14] and not fixed['viewport']['expanded'] and not np.count_nonzero(pixels[:,:24]) and not np.count_nonzero(pixels[:,264:])
            report['fixedRoomCentered']=True
            if args.baseline:p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'))
            else:
                path=[]
                for room in [35,10]:
                    if room==10:p.call('debugposition',40,144)
                    for attempt in range(5):
                        p.call('pulse',[203],650);time.sleep(.12)
                        meta=p.capture(f'install-{args.variant}-route-{room}-{attempt}',False,at_present=True)
                        path.append({'area':meta['area'],'room':meta['room'],'playState':meta['playState']})
                        if [meta['area'],meta['room'],meta['playState']]==[0,room,1]:break
                    else:raise RuntimeError('Could not reach actual slot1 cloud room')
                p.call('statesave','wide');report['actualSlot1Route']=path

            for direction,x,key in [('left',177,203),('right',335,205),('still',450,None)]:
                p.call('stateload','wide');m=p.capture('install-'+args.variant+'-source',True,at_present=True)
                assert [m['area'],m['room']]==[0,10],m
                p.call('debugmove',x,int(m['cameraY']+m['playerY']));time.sleep(.3)
                prefix=work/f'cloud-{pid}-{direction}'
                p.call('denseframes',str(prefix).replace('\\','/'),96,[] if key is None else [key],1100,False if args.baseline else 'objects')
                rows=json.loads(pathlib.Path(str(prefix)+'.frames.json').read_text())
                pixels=np.fromfile(str(prefix)+'.frames.rgb555',dtype='<u2').reshape(96,162,288)[:,1:161]&0x7fff
                sources=None if args.baseline else np.memmap(str(prefix)+'.ppu.bin',dtype='u1',mode='r',shape=(96,0x5f4b8))
                samples=[];proofs=[];directory=ROOT/f'diagnostics-v2/install-{args.variant}-{pid}-{direction}';directory.mkdir(exist_ok=True)
                for i,r in enumerate(rows):
                    assert [r['area'],r['room']]==[0,10],r
                    counts={}
                    for field in ['cloudNow','cloudPrevious']:
                        actors=r[field]['actors'] if r[field] else []
                        counts[field]=sum(any((o['a2']>>12)==e['palette'] and (o['a0']&255)==((e['y']//65536-8)&255) and ((o['a1']&511)-(e['x']//65536))&511 in [0,496,480] for e in actors) for o in r['cloudOam'])
                    expected={};actors=r['cloudPrevious']['actors']
                    for o in r['cloudOam']:
                        e=next(e for e in actors if (o['a2']>>12)==e['palette'] and (o['a0']&255)==((e['y']//65536-8)&255) and ((o['a1']&511)-(e['x']//65536))&511 in [0,496,480])
                        expected[o['o']]=(12*e['x']-11*(r['viewport']['left']-24)*65536)//(12*65536)-e['x']//65536
                    correctionErrors=[] if args.baseline else [o for o,c in expected.items() if r['cloudCorrections'][o]!=c]
                    samples.append({'i':i,'oam':len(r['cloudOam']),**counts,'correctionErrors':correctionErrors})
                    # Independently ask the unhooked native renderer to composite
                    # corrected hardware OAM with the native alpha coefficients.
                    if sources is not None and (i%8==0 or 40<=i<=54):
                        source=bytearray(sources[i]);assert struct.unpack_from('<I',source,0x2205c)[0]==0
                        for bg in [2,3]:
                            for off in [0x20810+bg*4,0x21ff8+bg*4]:
                                v=struct.unpack_from('<H',source,off)[0];struct.pack_into('<H',source,off,(v+r['corrections'][bg])&511)
                        for o,c in expected.items():
                            off=0x20002+o*8;v=struct.unpack_from('<H',source,off)[0];struct.pack_into('<H',source,off,(v&~511)|((v+c)&511))
                        references=[]
                        for tag in ['expected','no-cloud']:
                            if tag=='no-cloud':
                                for o in expected:struct.pack_into('<H',source,0x20000+o*8,0x200)
                            dst=work/f'cloud-proof-{pid}-{direction}-{i}-{tag}';pp=pathlib.Path(str(dst)+'.ppu');pp.write_bytes(source)
                            p.call('renderfile',str(dst).replace('\\','/'),str(tmp/'render-objects.dll').replace('\\','/'),str(pp).replace('\\','/'),'RenderSnapshot')
                            references.append(np.fromfile(str(dst)+'.shift0.rgb555',dtype='<u2').reshape(160,240)&0x7fff)
                        want,without=references;mask=want!=without
                        mask[:40]=False;mask[100:]=False
                        left=r['viewport']['left'];actual=pixels[i,:,left:left+240]
                        proof={'i':i,'visibleCloudPixels':int(mask.sum()),'wrong':int(np.sum(actual[mask]!=want[mask]))}
                        proofs.append(proof)
                        if proof['wrong']:
                            rgb=np.stack([(want>>n)&31 for n in [0,5,10]],axis=-1).astype(np.uint8);rgb=(rgb<<3)|(rgb>>2);Image.fromarray(rgb).resize((960,640),Image.Resampling.NEAREST).save(directory/f'{i:03}-expected.png')

                    if i%4==0:
                        frame=pixels[i];rgb=np.stack([(frame>>n)&31 for n in [0,5,10]],axis=-1).astype(np.uint8);rgb=(rgb<<3)|(rgb>>2)
                        Image.fromarray(rgb).resize((1152,640),Image.Resampling.NEAREST).save(directory/f'{i:03}.png')
                row={'direction':direction,'framePrefix':str(prefix),'frames':len(samples),'oam':sum(r['oam'] for r in samples),'nowAligned':sum(r['cloudNow'] for r in samples),'previousAligned':sum(r['cloudPrevious'] for r in samples),'samples':samples,'pixelProofs':proofs,'visibleCloudPixels':sum(q['visibleCloudPixels'] for q in proofs),'wrongCloudPixels':sum(q['wrong'] for q in proofs)}
                report['cases'].append(row);save();print(json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
            assert report['noIni']
            report['passed']=all(c['previousAligned']==c['oam'] and c['oam']>100 and all(not z['correctionErrors'] for z in c['samples']) and (args.baseline or c['visibleCloudPixels']>1000 and c['wrongCloudPixels']==0) for c in report['cases'])
        finally:p.call('stateload','user',False)
finally:
    subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=30);guard.wait(timeout=15)
    report['after']=hashes();report['realSavesUnchanged']=report['before']==report['after'];report['exit']=json.loads((ROOT/f'diagnostics-v2/game-exit-{pid}.json').read_text())
    report['passed']=report.get('passed',False) and report['realSavesUnchanged'] and report['exit']['exitCode']=='0x0';save();print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)
assert report['passed']
