"""Check real offscreen OAM pixels across the full 48-pixel edge viewport."""
from debug_config import debug_root
import json,os,pathlib,time,struct
import numpy as np
from harness import Probe,ROOT
tmp=debug_root();report={'coverage':'Active frozen native OAM reference compared with actual edge output. Empty engine OAM tuples are disabled only in the private reference snapshot; no live entity or ROM mutation.','samples':[]}
with Probe() as p:
    p.call('statesave','user')
    try:
        bosses=['bossrush-room-'+x for x in ['084fb1e4','084fb27c','084fb324','084fb3bc','084fb454','084fb4ec','084fb63c']]
        for fixture in ['user-slot3-right-edge','v8-wide',*bosses]:
            p.call('stateimport',fixture,str(tmp/fixture).replace('\\','/'))
        cases=[('user-slot3-right-edge',450,'left',2),*[(f,450,'left',14) for f in bosses],('v8-wide',70,'right',12)]
        for fixture,x,side,attempts in cases:
            if side in {r['side'] for r in report['samples'] if r['visibleMatching']>=10}:continue
            p.call('stateload',fixture);meta=p.capture('edge-objects-source',True,at_present=True);y=meta['cameraY']+meta['playerY']
            p.call('debugposition',x,y)
            for i in range(attempts):
                p.call('pulse',[45],120);time.sleep(.1)
                label=f'edge-objects-{fixture}-{side}-{i}';meta=p.capture(label,True,at_present=True,scan_reference=True);left=meta['viewport']['left']
                if left!=(48 if side=='left' else 0):continue
                source=bytearray((tmp/(label+'.scan.ppu')).read_bytes());unused=0
                for o in range(128):
                    if struct.unpack_from('<3H',source,0x20000+o*8)==(0,0x1e0,0):struct.pack_into('<H',source,0x20000+o*8,0x200);unused+=1
                active_path=tmp/(label+'-active.ppu');active_path.write_bytes(source)
                p.call('renderfile',str(tmp/label).replace('\\','/'),str(tmp/'render-objects.dll').replace('\\','/'),str(active_path).replace('\\','/'))
                reference=np.fromfile(tmp/f'{label}.shift{-48 if side=="left" else 48}.rgb555',dtype='<u2').reshape(160,240)
                reference=reference[:,:48] if side=='left' else reference[:,192:]
                actual=np.fromfile(tmp/f'{label}.rgb555',dtype='<u2').reshape(162,288)[1:161]
                actual=actual[:,:48] if side=='left' else actual[:,240:]
                mask=(reference&0x7fff)!=0;matching=int(np.count_nonzero(mask&(reference==actual)))
                row={'label':label,'side':side,'viewport':meta['viewport'],'unusedSlotsExcluded':unused,'objectPixels':int(mask.sum()),'visibleMatching':matching};report['samples'].append(row);print(json.dumps(row),flush=True)
                if matching>=10:break
    finally:p.call('stateload','user',False)
report['provenSides']=sorted({r['side'] for r in report['samples'] if r['visibleMatching']>=10});report['passed']=report['provenSides']==['left','right']
(ROOT/'diagnostics-v2/edge-objects-check.json').write_text(json.dumps(report,indent=2));assert report['passed'],report
