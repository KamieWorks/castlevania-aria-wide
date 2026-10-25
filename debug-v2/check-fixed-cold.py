"""Capture fixed-room expansion from a single proxy loaded at Steam startup."""
from debug_config import debug_root
import json,os,pathlib,time,argparse
import numpy as np
from PIL import Image,ImageDraw
from harness import Probe,ROOT
parser=argparse.ArgumentParser();parser.add_argument('--version',default='v16');args=parser.parse_args();assert args.version in ['v12','v13','v16','v19','v20']
tmp=debug_root();report={'version':args.version}
with Probe() as p:
    report['patchBefore']=p.call('patchstatus');report['start']=p.call('stats')
    assert report['start']['module']=='d3d9.dll',report
    for name,fixture in [('boss','chaos-boss'),('save','julius-save-room')]:
        p.call('stateimport',name,str(tmp/fixture).replace('\\','/'));p.call('stateload',name);time.sleep(.18)
        label=f'{args.version}-fixed-{name}';meta=p.capture(label,True,at_present=True)
        assert (meta['width'],meta['height'])==(288,162),meta
        raw=(ROOT/'private-v2/captures'/f'{label}.ppu').read_bytes();frame=(int.from_bytes(raw[0x5e064:0x5e068],'little')+2)%3
        native=np.frombuffer(raw,dtype='<u2',count=40960,offset=0x22064+frame*0x14000).reshape(160,256)[:,:240]
        output=np.fromfile(ROOT/'private-v2/captures'/f'{label}.rgb555',dtype='<u2').reshape(162,288)
        assert np.array_equal(native,output[1:161,24:264])
        report[name]={'centerEqual':True,'sideNonzero':[int(np.count_nonzero(output[1:161,:24])),int(np.count_nonzero(output[1:161,264:]))],'room':[meta['area'],meta['room']]}
    report['end']=p.call('stats');report['status']=p.call('status')
    assert report['end']['frames']>report['start']['frames']
    assert report['boss']['sideNonzero'][0]>1000 and report['boss']['sideNonzero'][1]>1000,report
    report['passed']=True
canvas=Image.new('RGB',(1152,1352),(20,20,20));draw=ImageDraw.Draw(canvas)
draw.text((12,7),'Before: v10 fixed-room boundary',fill='white');draw.text((12,683),f'After: {args.version} decorative edge reflection; original arena preserved',fill='white')
canvas.paste(Image.open(ROOT/'diagnostics-v2/v10-fixed-boss.png'),(0,28));canvas.paste(Image.open(ROOT/f'diagnostics-v2/{args.version}-fixed-boss.png'),(0,704))
canvas.save(ROOT/'diagnostics-v2/fixed-boss-before-after.png')
(ROOT/f'diagnostics-v2/fixed-cold-{args.version}-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
