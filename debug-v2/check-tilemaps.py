"""Compare decoded room metatiles to resident VRAM before using screen-edge repairs."""
from pathlib import Path
import struct,json,argparse
from harness import ROOT
p=argparse.ArgumentParser();p.add_argument('capture');a=p.parse_args()
e=(ROOT/f'private-v2/captures/{a.capture}.ewram').read_bytes();v=(ROOT/f'private-v2/captures/{a.capture}.ppu').read_bytes()
r=(ROOT/'private-v2/archive/patchdata.psb.m_extracted/system/roms/03_Akatsuki_JP.patch_210623m.bin').read_bytes()
def resolve(address,length):
    if 0x08000000<=address and address+length<=0x08000000+len(r):return r[address-0x08000000:address-0x08000000+length]
    if 0x02000000<=address and address+length<=0x02000000+len(e):return e[address-0x02000000:address-0x02000000+length]
    raise ValueError(hex(address))
def u16(buf,off):return struct.unpack_from('<H',buf,off)[0]
def u32(buf,off):return struct.unpack_from('<I',buf,off)[0]
for bg in range(1,4):
    if not u32(e,0xa078+bg*28):
        print(json.dumps({'bg':bg,'absent':True}));continue
    info=0xa078+bg*28;meta=resolve(u32(e,info),16);w,h=meta[:2];flags=u16(meta,2);camx=u16(e,info+6);camy=u16(e,info+10)
    blocks=resolve(u32(meta,12),w*h*8*8*2)
    table=resolve(0x02000000+(0xa108 if bg==1 else 0xc0ec),0x1fe4) if flags&2 else resolve(u32(meta,4),0x2000)
    ctrl=u16(v,0x21fe8+8+bg*2);base=(ctrl&0x1f00)*8;hx=u16(v,0x21ff8+bg*4);hy=u16(v,0x21ffa+bg*4)
    hits=total=0;examples=[]
    for y in range(0,160,8):
        for x in range(0,240,8):
            tx=(camx+x)//8;ty=(camy+y)//8
            if tx>=w*32 or ty>=h*32:continue
            b=u16(blocks,((ty//4)*w*8+tx//4)*2)
            if b&0x3fff:
                sx=tx%4;sy=ty%4
                if b&0x4000:sx=3-sx
                if b&0x8000:sy=3-sy
                off=(((b&0x3fff)-1)*16+sy*4+sx)*2
                if off+2>len(table):continue
                expected=u16(table,off)^((b&0xc000)>>4)
            else:expected=0
            observed=u16(v,base+((((hy+y)//8)&31)*32+(((hx+x)//8)&31))*2)
            total+=1;hits+=expected==observed
            if expected!=observed and len(examples)<4:examples.append([x,y,hex(expected),hex(observed)])
    print(json.dumps({'bg':bg,'room':[w,h],'camera':[camx,camy],'hardwareScroll':[hx,hy],'control':hex(ctrl),'matched':hits,'total':total,'examples':examples}))
