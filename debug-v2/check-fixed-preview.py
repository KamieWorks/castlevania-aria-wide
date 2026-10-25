"""Same private fixtures before/after expansion, including a real code rollback."""
from debug_config import debug_root
import json,os,pathlib,time
import numpy as np
from PIL import Image,ImageDraw
from harness import Probe,ROOT
tmp=debug_root()
report={'scenes':[]}
def record(p,name,state):
    p.call('stateload',state);time.sleep(.18)
    meta=p.capture(name,True,at_present=True)
    raw=(ROOT/'private-v2/captures'/f'{name}.ppu').read_bytes();i=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
    assert int.from_bytes(raw[0x2205c:0x22060],'little')==0
    center=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+i*0x14000).reshape(160,256)[:,:240]
    output=np.fromfile(ROOT/'private-v2/captures'/f'{name}.rgb555',dtype='<u2').reshape(162,288)
    assert np.array_equal(center,output[1:161,24:264])
    return {'name':name,'area':meta['area'],'room':meta['room'],'player':[meta['playerX'],meta['playerY']],'camera':[meta['cameraX'],meta['cameraY']],'centerEqual':True,'sideNonzero':[int(np.count_nonzero(output[1:161,:24])),int(np.count_nonzero(output[1:161,264:]))]}
with Probe() as p:
    p.call('stateimport','boss',str(tmp/'chaos-boss').replace('\\','/'));p.call('stateimport','save',str(tmp/'julius-save-room').replace('\\','/'))
    for state in ('boss','save'):report['scenes'].append(record(p,f'v10-fixed-{state}',state))
    report['install']=p.call('hotreplace',str(tmp/'realtime-v11.dll').replace('\\','/'))
    for state in ('boss','save'):report['scenes'].append(record(p,f'v11-fixed-{state}',state))
    # Actually reinstall the previous native module, then verify the old margin.
    report['rollback']=p.call('hotreplace',str(tmp/'realtime-v10.dll').replace('\\','/'))
    rollback=record(p,'v10-rollback-boss','boss');assert rollback['sideNonzero']==[0,0],rollback
    report['scenes'].append(rollback)
    report['resume']=p.call('hotreplace',str(tmp/'realtime-v11.dll').replace('\\','/'))
    record(p,'v11-preview-safe','save')
    report['passed']=True
# Native central art is unchanged; arrange existing captures as a simple visual comparison.
canvas=Image.new('RGB',(1152,648*2+56),(20,20,20));draw=ImageDraw.Draw(canvas)
draw.text((12,7),'v10: original fixed-room boundary',fill='white');draw.text((12,648+35),'v11: background + offscreen rendering; original arena preserved',fill='white')
canvas.paste(Image.open(ROOT/'diagnostics-v2/v10-fixed-boss.png'),(0,28));canvas.paste(Image.open(ROOT/'diagnostics-v2/v11-fixed-boss.png'),(0,648+56))
canvas.save(ROOT/'diagnostics-v2/fixed-boss-before-after.png')
(ROOT/'diagnostics-v2/fixed-preview-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
