"""Read-only GBA text-layer decoder, calibrated against native BG3 scanlines."""
import numpy as np

def layer(source,row,bg,width=288,expanded=True):
    ctrl=row['control'][bg];assert not ctrl&0xc000,'Unvalidated screen size'
    p=np.frombuffer(source,dtype='u1');words=np.frombuffer(source,dtype='<u2')
    regs=np.asarray(row['lineScroll'],dtype=np.int64)
    offset=row['corrections'][bg]-row['viewport']['left'] if expanded else 0
    xx=(np.arange(width)[None,:]+regs[:,bg*2,None]+offset)&255
    yy=(np.arange(160)[:,None]+regs[:,bg*2+1,None])&255
    tile=words[((ctrl&0x1f00)*8+(yy//8*32+xx//8)*2)//2]
    tx=np.where(tile&0x400,7-(xx&7),xx&7);ty=np.where(tile&0x800,7-(yy&7),yy&7)
    if ctrl&128:
        color=p[(ctrl&12)*4096+(tile&1023)*64+ty*8+tx];index=color
    else:
        packed=p[(ctrl&12)*4096+(tile&1023)*32+ty*4+tx//2]
        color=(packed>>(4*(tx&1)))&15;index=(tile>>12)*16+color
    rgb=words[0x20400//2+index]&0x7fff
    return rgb,color!=0

def compare(source,row,native,actual):
    assert row['blendMode']==0 and row['flags']&7==0
    ref,valid=layer(source,row,3,240,False)
    nativeValid=(native&0x80000000)==0
    calibration=int(np.sum(valid!=nativeValid)+np.sum(ref[valid&nativeValid]!=(native[valid&nativeValid]&0x7fff)))
    rgb,mask=layer(source,row,3)
    mask[:128]=False
    left=row['viewport']['left'];mask[:,:left]=False;mask[:,left+240:]=False
    for bg in [0,1,2]:
        if row['flags']&(0x100<<bg):
            _,opaque=layer(source,row,bg);mask&=~opaque
    # Conservative hardware object bounds; no world/entity mutation.
    oam=np.frombuffer(source,dtype='<u2',count=512,offset=0x20000).reshape(128,4)
    sizes=[[(8,8),(16,16),(32,32),(64,64)],[(16,8),(32,8),(32,16),(64,32)],[(8,16),(8,32),(16,32),(32,64)]]
    for a0,a1,a2,_ in oam.astype(int):
        if (a0,a1,a2)==(0,0x1e0,0) or a0&0x300==0x200 or a0>>14==3:continue
        w,h=sizes[a0>>14][a1>>14]
        if a0&0x300==0x300:w*=2;h*=2
        x=a1&511;x=x-512 if x>=256 else x;x+=left
        y=a0&255;y=y-256 if y>=160 else y
        if x+w<0 or x>=288 or y+h<0 or y>=160:continue
        mask[max(0,y-3):min(160,y+h+3),max(0,x-3):min(288,x+w+3)]=False
    mismatch=mask&(rgb!=actual)
    return calibration,int(mask.sum()),int(mismatch.sum()),rgb,mask
