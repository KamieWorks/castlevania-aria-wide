from debug_config import debug_root
import pathlib,os,json,time,argparse
import numpy as np
from PIL import Image
from harness import Probe,ROOT
p=argparse.ArgumentParser();p.add_argument('--dll',default='realtime.dll');p.add_argument('--seconds',type=float,default=3);a=p.parse_args()
tmp=debug_root()
with Probe() as probe:
    try:
        print(probe.call('install',str(tmp/a.dll).replace('\\','/')))
        time.sleep(a.seconds)
        meta=probe.call('capturewide',str(tmp/'realtime').replace('\\','/'))
        pixels=np.frombuffer((tmp/'realtime.rgb555').read_bytes(),dtype='<u2').reshape(162,288)
        rgb=np.stack([(pixels>>n)&31 for n in (0,5,10)],axis=-1).astype(np.uint8)
        Image.fromarray((rgb<<3)|(rgb>>2)).resize((1152,648),Image.Resampling.NEAREST).save(ROOT/'diagnostics-v2/realtime.png')
        print(json.dumps(meta));(ROOT/'diagnostics-v2/realtime.json').write_text(json.dumps(meta,indent=2))
    finally:print({'uninstall':probe.call('cleanup')})
