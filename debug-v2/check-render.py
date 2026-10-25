from debug_config import debug_root
import os,pathlib,json
import numpy as np
from PIL import Image
from harness import Probe,ROOT

def image555(path):
    a=np.frombuffer(path.read_bytes(),dtype='<u2').reshape(160,240)
    rgb=np.stack([(a>>n)&31 for n in (0,5,10)],axis=-1).astype(np.uint8)
    return Image.fromarray((rgb<<3)|(rgb>>2))

tmp=debug_root()
with Probe() as p:
    p.capture('render-live',True)
    print(p.call('render',str(tmp/'prototype').replace('\\','/'),str(tmp/'render-prototype.dll').replace('\\','/')))
images=[image555(tmp/f'prototype.shift{s}.rgb555') for s in [0,-24,24]]
canvas=Image.new('RGB',(720,160))
for i,im in enumerate(images):canvas.paste(im,(i*240,0))
canvas.resize((1440,320),Image.Resampling.NEAREST).save(ROOT/'diagnostics-v2/render-prototype-comparison.png')
wide=Image.new('RGB',(288,160));wide.paste(images[1].crop((0,0,24,160)),(0,0));wide.paste(images[0],(24,0));wide.paste(images[2].crop((216,0,240,160)),(264,0))
wide.resize((1152,640),Image.Resampling.NEAREST).save(ROOT/'diagnostics-v2/render-prototype-wide.png')
print(json.dumps({'seamLeftMatch':float(np.mean(np.array(images[1])[:,24:]==np.array(images[0])[:,:216])),'seamRightMatch':float(np.mean(np.array(images[2])[:,:216]==np.array(images[0])[:,24:]))}))
