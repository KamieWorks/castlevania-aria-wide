"""Read-only geometry/layout comparison of the user's three extracted ROMs."""
import hashlib,json,struct
from harness import ROOT
paths={'JP-translated':ROOT/'private-v2/archive/patchdata.psb.m_extracted/system/roms/03_Akatsuki_JP.patch_210623m.bin'}
for region in ('US','EU'):paths[region]=ROOT/f'private-v2/archive/alldata.psb.m_extracted/system/roms/03_Akatsuki_{region}.patch_210623m.bin'
signature=paths['JP-translated'].read_bytes()[0x197c:0x198c];results={};tables={}
for name,path in paths.items():
    rom=path.read_bytes()
    def read(p,size):
        offset=p-0x08000000
        if offset<0 or offset+size>len(rom):raise ValueError(hex(p))
        return rom[offset:offset+size]
    def u32(p):return struct.unpack('<I',read(p,4))[0]
    matches=[i for i in range(0,0x40000,2) if rom[i:i+16]==signature];assert len(matches)==1,matches
    function=0x08000000+matches[0];table=u32(function+16)
    areas=[u32(table+i*4) for i in range(12)]+[table];rooms=[]
    for area,start in enumerate(areas[:-1]):
        delta=areas[area+1]-start;assert 0<delta<=256 and delta%4==0
        for index in range(delta//4):
            pointer=u32(start+index*4);header=read(pointer,36);layers=u32(pointer+8);main=u32(layers+8);meta=read(main,16) if main else None
            width,height=(meta[0],meta[1]) if meta else (None,None)
            if meta:assert 1<=width<=64 and 1<=height<=64
            blockmap=read(struct.unpack_from('<I',meta,12)[0],width*height*128) if meta else b''
            rooms.append({'area':area,'room':index,'header':hex(pointer),'size':[width,height],'mode':header[0]&7,'blockmapSha256':hashlib.sha256(blockmap).hexdigest() if meta else None})
    geometry=[{k:r[k] for k in ('area','room','size','mode','blockmapSha256')} for r in rooms]
    tables[name]=geometry
    results[name]={'romCode':rom[0xac:0xb0].decode(),'romSha256':hashlib.sha256(rom).hexdigest(),'getRoomPointer':hex(function),'areaTable':hex(table),'roomCount':len(rooms),'rooms':rooms,
                   'absoluteRamLiterals':{hex(a):rom.count(struct.pack('<I',a)) for a in (0x02000010,0x02000064,0x02000088,0x0200a078,0x0200a094)}}
comparisons={}
reference=tables['JP-translated']
for name,geometry in tables.items():
    assert len(geometry)==len(reference)
    shape_diffs=[];map_diffs=[]
    for a,b in zip(reference,geometry):
        if any(a[k]!=b[k] for k in ('area','room','size','mode')):shape_diffs.append({'JP':a,'region':b})
        elif a['blockmapSha256']!=b['blockmapSha256']:map_diffs.append({'area':a['area'],'room':a['room']})
    comparisons[name]={'shapeDifferences':shape_diffs,'blockmapDifferences':map_diffs,'sameMainRoomGeometry':not shape_diffs and not map_diffs}
report={'coverage':'Static room dimensions, display modes and blockmaps; does not replace region runtime testing.','regions':results,'comparisons':comparisons}
(ROOT/'diagnostics-v2/region-static-layout-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({'regions':{n:{k:v for k,v in r.items() if k!='rooms'} for n,r in results.items()},'comparisons':comparisons}))
