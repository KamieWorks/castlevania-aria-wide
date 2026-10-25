"""Prove actual sprites render in the added margins, using frozen OAM controls."""
from debug_config import debug_root
import json,os,pathlib,time,struct
import numpy as np
from PIL import Image
from harness import Probe,ROOT
tmp=debug_root()
results=[]
def image(a,path):
    rgb=np.stack([(a>>n)&31 for n in (0,5,10)],axis=-1).astype(np.uint8);Image.fromarray((rgb<<3)|(rgb>>2)).resize((1152,640),Image.Resampling.NEAREST).save(path)
with Probe() as p:
    p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'))
    p.call('stateimport','safe',str(tmp/'julius-save-room').replace('\\','/'))
    p.call('stateload','wide')
    try:
        for i in range(10):
            p.call('pulse',[205 if i<5 else 203],120)
            label=f'offscreen-{i}';meta=p.capture(label,True,at_present=True)
            p.call('renderfile',str(tmp/label).replace('\\','/'),str(tmp/'render-objects.dll').replace('\\','/'),str(tmp/(label+'.ppu')).replace('\\','/'))
            left=np.fromfile(tmp/f'{label}.shift-24.rgb555',dtype='<u2').reshape(160,240)[:,:24]
            right=np.fromfile(tmp/f'{label}.shift24.rgb555',dtype='<u2').reshape(160,240)[:,216:240]
            actual=np.fromfile(tmp/f'{label}.rgb555',dtype='<u2').reshape(162,288)[1:161]
            # Restrict proof to world pixels within the physical room boundary.
            valid=[meta['cameraX']>=24,meta['cameraX']+264<=512]
            counts=[]
            for index,(reference,observed) in enumerate([(left,actual[:,:24]),(right,actual[:,264:])]):
                mask=(reference&0x7fff)!=0
                counts.append({'objectPixels':int(mask.sum()) if valid[index] else 0,'visibleMatching':int(np.count_nonzero(mask&(reference==observed))) if valid[index] else 0})
            row={'sample':i,'cameraX':meta['cameraX'],'sides':counts};results.append(row);print(json.dumps(row),flush=True)
            if any(c['visibleMatching']>=10 for c in counts):
                canvas=np.zeros((160,288),dtype='<u2');canvas[:,:24]=left;canvas[:,264:]=right
                image(canvas,ROOT/'diagnostics-v2/offscreen-objects-isolated.png')
                report={'passed':True,'proofSample':label,'samples':results}
                break
        else:raise AssertionError('No verified visible offscreen sprite in sampled walk')
    finally:p.call('stateload','safe')
(ROOT/'diagnostics-v2/offscreen-objects-check.json').write_text(json.dumps(report,indent=2))
