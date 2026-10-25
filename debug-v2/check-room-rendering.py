"""Doorway-based rendering smoke coverage, not a claim of room completion."""
from debug_config import debug_root
import argparse,json,os,pathlib,time,hashlib
import numpy as np
from harness import Probe,ROOT,EXE
parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=[0,1],default=1);parser.add_argument('--limit',type=int,default=500);args=parser.parse_args()
tmp=debug_root()
rooms=[r for r in json.loads((ROOT/'private-v2/room-graph.json').read_text()) if r['mode']==args.mode and not r['specialWithoutMap']][:args.limit]
report={'coverage':'Native doorway rendering smoke; private runtime doorway redirection. Not full gameplay or boss-completion coverage.','proxySha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest(),'samples':[]}
out=ROOT/f'diagnostics-v2/room-render-mode{args.mode}-check.json'
with Probe() as p:
    p.call('stateimport','source',str(tmp/'v8-wide').replace('\\','/'));p.call('stateimport','safe',str(tmp/'julius-save-room').replace('\\','/'))
    try:
        for target in rooms:
            row={'target':hex(target['pointer']),'identities':target['identities'],'size':[target['width'],target['height']]}
            try:
                p.call('stateload','source');p.call('debugdoor',1,target['pointer'])
                p.call('debugentry',target['pointer'],min(1900,target['width']*128),160)
                p.call('debugposition',495,191);p.call('pulse',[205],850);time.sleep(.2);p.call('restoredoors')
                label=f'room-smoke-{target["pointer"]:08x}';meta=p.capture(label,True,at_present=True)
                ram=(ROOT/f'private-v2/captures/{label}.ewram').read_bytes();actual=int.from_bytes(ram[0x88:0x8c],'little')
                row.update(actual=hex(actual),playState=meta['playState'],viewport=meta['viewport'],hardwareMode=meta['dispcnt']&7)
                if actual!=target['pointer']:raise RuntimeError('Native transition selected another room or room variant')
                if meta['playState']!=1:raise RuntimeError('Room has not reached ordinary gameplay')
                if meta['dispcnt']&7!=target['mode']:raise RuntimeError('Hardware mode differs from room header')
                view=meta['viewport'];assert view and view['expanded'],view
                left=view['left'];raw=(ROOT/f'private-v2/captures/{label}.ppu').read_bytes();i=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
                assert int.from_bytes(raw[0x2205c:0x22060],'little')==0,'This smoke comparison requires native blend mode zero'
                native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+i*0x14000).reshape(160,256)[:,:240]
                output=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
                assert np.array_equal(native,output[1:161,left:left+240]),'Native raster mismatch'
                row.update(centerEqual=True,passed=True,sideNonzero=[int(np.count_nonzero(output[1:161,:left])),int(np.count_nonzero(output[1:161,left+240:]))])
            except Exception as e:row.update(passed=False,error=str(e))
            finally:p.call('restoredoors')
            report['samples'].append(row);out.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
    finally:p.call('restoredoors');p.call('stateload','safe')
report['passedCount']=sum(r['passed'] for r in report['samples']);report['testedCount']=len(report['samples']);out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'passedCount':report['passedCount'],'testedCount':report['testedCount']}),flush=True)
