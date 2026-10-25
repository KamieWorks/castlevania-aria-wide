"""Exercise all four native blend modes and the patch's serialized margin history."""
from debug_config import debug_root
import json,os,pathlib,time,shutil
import numpy as np
from harness import Probe,ROOT
tmp=debug_root()
report=[]
def verify(label):
    raw=(ROOT/'private-v2/captures'/f'{label}.ppu').read_bytes()
    word=lambda o:int.from_bytes(raw[o:o+4],'little')
    i=(word(0x5e064)+2)%3
    frames=[np.frombuffer(raw,dtype='<u2',count=256*160,offset=0x22064+j*0x14000).reshape(160,256)[:,:240].astype(np.uint32) for j in range(3)]
    cur,prev,prior=frames[i],frames[(i+2)%3],frames[(i+1)%3]
    mode=word(0x2205c);average=((prev^cur)>>1&0x3def)+(prev&cur)
    if mode==0:expected=cur
    elif mode==1:expected=average
    elif mode==2:expected=np.where(((prior^cur)&0x7fff)==0,average,cur)
    else:
        phase=word(0x5f4a0)^1;coeff=word(0x5f4a4);weight=coeff if phase==0 else 256-coeff
        a,b=weight>>3,(256-weight)>>3
        expected=((((prev&0x3e0)*b>>5)&0x3e0)+(((cur&0x3e0)*a>>5)&0x3e0))|((((prev&0x7c1f)*b>>5)&0x7c1f)+(((cur&0x7c1f)*a>>5)&0x7c1f))
    out=np.fromfile(ROOT/'private-v2/captures'/f'{label}.rgb555',dtype='<u2').reshape(162,288)
    meta=json.loads((ROOT/f'diagnostics-v2/{label}.json').read_text());view=meta.get('viewport')
    left=view['left'] if view and view['expanded'] else 24
    equal=bool(np.array_equal(expected,out[1:161,left:left+240]));assert equal,(label,np.mean(expected==out[1:161,left:left+240]))
    return equal
with Probe() as p:
    print(p.call('stats'),flush=True)
    p.call('stateimport','fixture',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','fixture')
    for mode in range(4):
        p.call('debugblend',mode);p.call('pulse',[205],150)
        label=f'blend-{mode}';p.capture(label,True,at_present=True)
        r={'mode':mode,'centerEqual':verify(label)}
        saved=p.call('statesave',f'save-{mode}');r['records']=saved['records']
        p.call('pulse',[203],180)
        p.call('statereloadsave',f'save-{mode}',f'copy-{mode}')
        compare=p.call('statecompare',f'save-{mode}',f'copy-{mode}');r['changes']=compare['changes']
        assert not any(c['name']=='ARIA-WIDE-1' for c in compare['changes']),r
        r['historyEqual']=True;p.capture(f'blend-{mode}-restored',True,at_present=True)
        report.append(r);print(json.dumps(r),flush=True)
(ROOT/'diagnostics-v2/blend-state-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
