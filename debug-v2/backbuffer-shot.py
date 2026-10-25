from debug_config import debug_root
"""Capture the verified game's hidden D3D9 backbuffer without activating it."""
import argparse,json,os,pathlib,subprocess
from PIL import Image
from harness import identify,ROOT
parser=argparse.ArgumentParser();parser.add_argument('label');args=parser.parse_args()
assert args.label.replace('-','').replace('_','').isalnum()
pid=identify();raw=debug_root()/'backbuffer.bgra'
result=subprocess.run(['node',str(ROOT/'debug-v2/backbuffer-shot.mjs'),str(pid),str(raw).replace('\\','/')],capture_output=True,text=True,check=True,timeout=16,creationflags=subprocess.CREATE_NO_WINDOW)
meta=json.loads(result.stdout);meta['pid']=pid
image=Image.frombytes('RGB',(meta['width'],meta['height']),raw.read_bytes(),'raw','BGRX');image.save(ROOT/f'diagnostics-v2/{args.label}.png')
(ROOT/f'diagnostics-v2/{args.label}.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
