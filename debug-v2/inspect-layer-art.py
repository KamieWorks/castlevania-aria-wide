"""Decode private native VRAM layers for asset-role inspection; never distribute."""
import pathlib,struct
import numpy as np
from PIL import Image
from harness import ROOT
v=(ROOT/'private-v2/captures/chaos-boss-action.ppu').read_bytes()
palette=np.frombuffer(v,dtype='<u2',count=256,offset=0x20400)
for bg in (1,2):
    ctrl=struct.unpack_from('<H',v,0x21ff0+bg*2)[0];screen=(ctrl&0x1f00)*8;chars=(ctrl&12)*0x1000
    out=np.zeros((256,256),dtype=np.uint16)
    for y in range(256):
        for x in range(256):
            if bg==2:
                tile=v[screen+y//8*32+x//8];index=v[chars+tile*64+(y%8)*8+x%8]
            else:
                tile=struct.unpack_from('<H',v,screen+(y//8*32+x//8)*2)[0];sx=x%8;sy=y%8
                if tile&0x400:sx=7-sx
                if tile&0x800:sy=7-sy
                packed=v[chars+(tile&1023)*32+sy*4+sx//2];index=(packed>>((sx&1)*4))&15
                if index:index+=(tile>>12)*16
            out[y,x]=palette[index]
    rgb=np.stack([(out>>n)&31 for n in (0,5,10)],axis=-1).astype(np.uint8)
    path=ROOT/'private-v2'/f'chaos-bg{bg}.png';Image.fromarray((rgb<<3)|(rgb>>2)).resize((768,768),Image.Resampling.NEAREST).save(path)
    print({'layer':bg,'control':hex(ctrl),'colors':len(np.unique(out)),'path':str(path)})
