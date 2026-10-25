"""Regression: the native unused-sprite convention must stay invisible in FOV.

Use the original object renderer on an unused-only frozen snapshot to obtain
the exact stray pixels. The v19 client capture must expose them; v20 must not.
Live OAM and the original central raster must remain unmodified.
"""
from debug_config import debug_root
import json,os,pathlib,struct,time
import numpy as np
from harness import Probe,ROOT
tmp=debug_root();report={'samples':[]}
with Probe() as p:
    p.call('statesave','user')
    try:
        p.call('stateimport','edge',str(tmp/'user-slot3-right-edge').replace('\\','/'));p.call('stateload','edge');time.sleep(.3)
        live=p.capture('unused-oam-v20',True,at_present=True);assert live['viewport']['left']==48,live
        for name,label,ppu_path,rgb_path in [
            ('old-v19','unused-only-v19',ROOT/'private-v2/captures/v19-unused-oam-baseline.ppu',ROOT/'private-v2/captures/v19-unused-oam-baseline.rgb555'),
            ('current','unused-only-current',ROOT/'private-v2/captures/unused-oam-v20.ppu',ROOT/'private-v2/captures/unused-oam-v20.rgb555')]:
            original=ppu_path.read_bytes();source=bytearray(original);unused=[]
            for o in range(128):
                offset=0x20000+o*8;attrs=struct.unpack_from('<3H',source,offset)
                if attrs==(0,0x1e0,0):unused.append(o)
                else:struct.pack_into('<H',source,offset,(attrs[0]&~0x100)|0x200)
            assert len(unused)>50,'The original inactive hardware slots must still be present'
            path=tmp/(label+'.ppu');path.write_bytes(source)
            p.call('renderfile',str(tmp/label).replace('\\','/'),str(tmp/'render-objects.dll').replace('\\','/'),str(path).replace('\\','/'))
            reference=np.fromfile(tmp/(label+'.shift-48.rgb555'),dtype='<u2').reshape(160,240)[:,:48]&0x7fff
            channels=np.stack([(reference>>n)&31 for n in (0,5,10)],axis=-1).astype(np.int16)
            mask=(channels.max(axis=-1)-channels.min(axis=-1))>6;assert int(mask.sum())>0
            output=np.fromfile(rgb_path,dtype='<u2').reshape(162,288);matching=int(np.count_nonzero(mask&(reference==(output[1:161,:48]&0x7fff))))
            row={'name':name,'nativeUnusedSlots':len(unused),'coloredUnusedPixels':int(mask.sum()),'strayMatchingPixels':matching};report['samples'].append(row)
            if name=='old-v19':assert matching>0,'The archived v19 capture must reproduce the bug'
            else:
                assert matching==0,'Unused native OAM leaked into the wider viewport'
                frame=(int.from_bytes(original[0x5e064:0x5e068],'little')+2)%3
                center=np.frombuffer(original,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
                assert np.array_equal(center,output[1:161,48:288]);row['centerEqual']=True
        report['passed']=True
    finally:p.call('stateload','user',False)
(ROOT/'diagnostics-v2/unused-oam-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
