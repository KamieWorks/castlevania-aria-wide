"""Check affine horizontal translation with independent frozen-PPU renders."""
from debug_config import debug_root
import os,pathlib,time,json
import numpy as np
from harness import Probe,ROOT
tmp=debug_root()
with Probe() as p:
    p.call('stateimport','affine',str(tmp/'mode1-room').replace('\\','/'));p.call('stateload','affine')
    p.call('debugposition',280,120);time.sleep(.15)
    p.capture('affine-interior',True,at_present=True)
    m=json.loads((ROOT/'diagnostics-v2/affine-interior.json').read_text());assert m['dispcnt']&7==1,m
    print(p.call('render',str(tmp/'affine-check').replace('\\','/'),str(tmp/'render-affine.dll').replace('\\','/')))
    arrays=[np.fromfile(tmp/f'affine-check.shift{s}.rgb555',dtype='<u2').reshape(160,240) for s in [0,-24,24]]
    result={'mode':1,'leftOverlap':float(np.mean(arrays[1][:,24:]==arrays[0][:,:216])),'rightOverlap':float(np.mean(arrays[2][:,:216]==arrays[0][:,24:]))}
    assert result['leftOverlap']==result['rightOverlap']==1,result
    # Actual output still retains the native central frame.
    raw=(ROOT/'private-v2/captures/affine-interior.ppu').read_bytes();i=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
    center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+i*0x14000).reshape(160,256)[:,:240]
    out=np.fromfile(ROOT/'private-v2/captures/affine-interior.rgb555',dtype='<u2').reshape(162,288)
    left=m['viewport']['left'];result['centerEqual']=bool(np.array_equal(center,out[1:161,left:left+240]));assert result['centerEqual']
    p.call('statesave','interior',str(tmp/'mode1-interior').replace('\\','/'))
(ROOT/'diagnostics-v2/affine-overlap-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
