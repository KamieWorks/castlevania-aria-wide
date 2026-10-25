"""Read-only verification of native regional boot/gameplay captures."""
import argparse,json,pathlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('code',choices=['A2CE','A2CP']);ap.add_argument('labels',nargs='+');ap.add_argument('--movement',nargs=2);args=ap.parse_args()
report={'code':args.code,'coverage':'Native regional menu and gameplay captures, no cross-region CPU state imports.','samples':[]}
for label in args.labels:
    meta=json.loads((ROOT/f'diagnostics-v2/{label}.json').read_text());raw=(ROOT/f'private-v2/captures/{label}.ppu').read_bytes()
    assert meta['romCode']==args.code and [meta['width'],meta['height'],meta['pitch']]==[288,162,576],meta
    assert int.from_bytes(raw[0x2205c:0x22060],'little')==0
    frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
    center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
    actual=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
    view=meta['viewport'];left=view['left'] if view['expanded'] else 24
    assert np.array_equal(center,actual[1:161,left:left+240]),label
    report['samples'].append({'label':label,'centerEqual':True,'viewport':view,'mode':meta['gameMode'],'playState':meta['playState']})
assert any(s['viewport']['expanded'] for s in report['samples']),'No actual room raster verified'
if args.movement:
    before,after=[json.loads((ROOT/f'diagnostics-v2/{label}.json').read_text()) for label in args.movement]
    assert all(m['romCode']==args.code and m['gameMode']==4 and m['playState']==1 for m in [before,after])
    delta=(after['cameraX']+after['playerX'])-(before['cameraX']+before['playerX'])
    assert abs(delta)>10,'No verified player movement'
    report['movement']={'labels':args.movement,'worldXDelta':delta}
report['passed']=True
(ROOT/f'diagnostics-v2/region-runtime-{args.code}-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
