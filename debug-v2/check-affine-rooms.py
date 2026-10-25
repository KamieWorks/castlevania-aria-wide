"""Visit the other two horizontal affine rooms through native transitions."""
from debug_config import debug_root
import json,os,pathlib,time,shutil
import numpy as np
from harness import Probe,ROOT
tmp=debug_root()
targets=[(0x084eca68,3,5),(0x084f28d4,2,2)];report=[]
with Probe() as p:
    p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'))
    p.call('stateimport','safe',str(tmp/'julius-save-room').replace('\\','/'))
    try:
        for target,width,height in targets:
            p.call('stateload','wide');p.call('debugdoor',1,target)
            p.call('debugentry',target,120,160);p.call('debugposition',495,191)
            p.call('pulse',[205],850);time.sleep(.5);p.call('restoredoors')
            p.call('pulse',[205],800);p.call('pulse',[45],150)
            label=f'affine-room-{target:08x}';meta=p.capture(label,True,at_present=True)
            ram=(ROOT/'private-v2/captures'/f'{label}.ewram').read_bytes()
            observed=int.from_bytes(ram[0x88:0x8c],'little')
            assert observed==target,(hex(observed),hex(target),meta)
            assert meta['dispcnt']&7==1,meta
            raw=(ROOT/'private-v2/captures'/f'{label}.ppu').read_bytes()
            frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
            center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
            output=np.fromfile(ROOT/'private-v2/captures'/f'{label}.rgb555',dtype='<u2').reshape(162,288)
            left=meta['viewport']['left'];equal=bool(np.array_equal(center,output[1:161,left:left+240]));assert equal
            r={'room':hex(target),'size':[width,height],'area':meta['area'],'index':meta['room'],'camera':[meta['cameraX'],meta['cameraY']],'viewport':meta['viewport'],'centerEqual':equal,'sideNonzero':[int(np.count_nonzero(output[1:161,:left])),int(np.count_nonzero(output[1:161,left+240:]))]}
            p.call('statesave',label,str(tmp/label).replace('\\','/'))
            for ext in ('json','bin'):shutil.copy2(tmp/(label+'.state.'+ext),ROOT/'private-v2/states'/(label+'.state.'+ext))
            report.append(r);print(json.dumps(r),flush=True)
    finally:
        p.call('restoredoors');p.call('stateload','safe')
    report.append({'lifecycle':p.call('lifecycle'),'status':p.call('status')})
(ROOT/'diagnostics-v2/affine-rooms-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
