"""Verify camera-limit composition against native pixels using private fixtures."""
from debug_config import debug_root
import json,os,pathlib,time,ctypes,hashlib
import numpy as np
from PIL import Image,ImageDraw
from harness import Probe,ROOT,EXE
tmp=debug_root()
report={'samples':[],'installedDllSha256':hashlib.sha256((EXE.parent/'d3d9.dll').read_bytes()).hexdigest()}
def check(p,label,want=None):
    meta=p.capture(label,True,at_present=True);view=meta['viewport']
    assert view and view['expanded'],view
    # The viewport follows this raster's latched camera. Guest RAM can
    # already contain the next frame and is not a layout reference.
    left=view['left'];camera=view['camera'];width=view['width']
    expected=max(0,min(48,camera-max(0,min(width-288,camera-24)))) if width>=288 else 24
    assert left==expected,(view,meta)
    if want is not None:assert left==want,(view,meta)
    raw=(ROOT/f'private-v2/captures/{label}.ppu').read_bytes()
    current=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
    native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+current*0x14000).reshape(160,256)[:,:240]
    output=np.fromfile(ROOT/f'private-v2/captures/{label}.rgb555',dtype='<u2').reshape(162,288)
    assert np.array_equal(native,output[1:161,left:left+240]),label
    row={'label':label,'viewport':view,'centerEqual':True,'leftSidePixels':int(np.count_nonzero(output[1:161,:left])),'rightSidePixels':int(np.count_nonzero(output[1:161,left+240:])),'room':[meta['area'],meta['room']]}
    report['samples'].append(row);return meta
with Probe() as p:
    p.call('stateimport','user',str(tmp/'user-slot3-right-edge').replace('\\','/'));p.call('stateload','user');time.sleep(.25)
    check(p,'v14-user-right-edge',48)
    p.call('statesave','edge-v2');p.call('pulse',[203],200);p.call('statereloadsave','edge-v2','edge-roundtrip')
    compare=p.call('statecompare','edge-v2','edge-roundtrip')
    assert not any(row['name']=='ARIA-WIDE-1' for row in compare['changes']),compare
    report['historyRoundtrip']=True
    p.call('stateimport','wide',str(tmp/'v8-wide').replace('\\','/'));p.call('stateload','wide');time.sleep(.2)
    mid=check(p,'v14-middle',24);worldy=mid['cameraY']+mid['playerY']
    p.call('debugposition',70,worldy);time.sleep(.35)
    for attempt in range(8):
        if p.call('viewport')['left']==0:break
        time.sleep(.1)
    check(p,'v14-left-edge',0)
    p.call('stateload','user');time.sleep(.2);check(p,'v14-right-restored',48)
    report['stats']=p.call('stats');report['passed']=True
canvas=Image.new('RGB',(1152,1352),(20,20,20));draw=ImageDraw.Draw(canvas)
draw.text((12,7),'Before: fixed symmetric margins at right room boundary',fill='white')
canvas.paste(Image.open(ROOT/'diagnostics-v2/user-edge-before.png'),(0,28))
draw.text((12,683),'After: 288-pixel viewport clamped inside the room; native raster preserved',fill='white')
canvas.paste(Image.open(ROOT/'diagnostics-v2/v14-user-right-edge.png'),(0,704));canvas.save(ROOT/'diagnostics-v2/user-edge-before-after.png')
(ROOT/'diagnostics-v2/edge-framing-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
