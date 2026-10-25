"""Read-only room metadata audit of the user's privately extracted Aria ROM."""
import json,struct,collections,hashlib
from harness import ROOT
rom=(ROOT/'private-v2/archive/patchdata.psb.m_extracted/system/roms/03_Akatsuki_JP.patch_210623m.bin').read_bytes()
assert hashlib.sha256(rom).hexdigest()=='c38582310c6ddd643c0b338edd1e266223e9473d50d30fb1f6fc33ce35d673f0'
def read(p,size):
    o=p-0x8000000
    if o<0 or o+size>len(rom):raise ValueError(hex(p))
    return rom[o:o+size]
def u32(b,o):return struct.unpack_from('<I',b,o)[0]
# Exact JP GetRoomPointer at 0x0800197c loads the table literal at 0x0800198c.
# Twelve adjacent area lists end at that pointer table, allowing bounded counts.
table=u32(read(0x0800198c,4),0)
areas=[u32(read(table+i*4,4),0) for i in range(12)]+[table]
entries=[]
for area,start in enumerate(areas[:-1]):
    assert 0<areas[area+1]-start<=256 and (areas[area+1]-start)%4==0
    for room in range((areas[area+1]-start)//4):entries.append({'area':area,'room':room,'pointer':u32(read(start+room*4,4),0)})
assert next(e['pointer'] for e in entries if (e['area'],e['room'])==(0,10))==0x084e5e8c
assert next(e['pointer'] for e in entries if (e['area'],e['room'])==(11,18))==0x084f92a4
# Scripted ending scenes can be absent from the area lists and doorway graph.
# Exact JP retail event-driver literal at 0x08037bf8 points to 18 room roots.
event_table=u32(read(0x08037bf8,4),0)
event_roots=[u32(read(event_table+i*4,4),0) for i in range(18)]
# Actual JP debug-exit records include Boss Rush roots absent from the main
# area table and the story event table. Verify their embedded label pointers.
debug_exit=0x084bcad4
assert read(u32(read(debug_exit+12*16+12,4),0),13)==b' Boss Rush 1P'
debug_roots=[u32(read(debug_exit+i*16+8,4),0) for i in range(17)]
queue=collections.deque([e['pointer'] for e in entries]+event_roots+debug_roots);rooms={};errors=[]
while queue:
    p=queue.popleft()
    if p in rooms:continue
    try:
        h=read(p,36);count=struct.unpack_from('<H',h,28)[0]
        if count>64:raise ValueError('Implausible door count')
        layer=read(u32(h,8),36);main=u32(layer,8);meta=read(main,16) if main else None
        if meta and (not 1<=meta[0]<=64 or not 1<=meta[1]<=64):raise ValueError('Invalid room dimensions')
        doors=[]
        for i in range(count):
            d=read(u32(h,24)+i*16,16);dest=u32(d,0)
            doors.append({'destination':dest,'cell':list(struct.unpack_from('<bb',d,4)),'offset':list(struct.unpack_from('<HH',d,6)),'camera':list(struct.unpack_from('<HH',d,10))})
            queue.append(dest)
        ids=[{k:e[k] for k in ['area','room']} for e in entries if e['pointer']==p]
        rooms[p]={'pointer':p,'identities':ids,'width':meta[0] if meta else None,'height':meta[1] if meta else None,'specialWithoutMap':meta is None,'mode':h[0]&7,'doors':doors,'alternate':u32(h,4)}
        if u32(h,4):queue.append(u32(h,4))
    except Exception as e:errors.append({'pointer':hex(p),'error':str(e)})
summary={'sha256':hashlib.sha256(rom).hexdigest(),'areaTable':hex(table),'tableEntries':len(entries),'rooms':len(rooms),'scriptEventRoots':[hex(p) for p in event_roots],'debugExitRoots':[hex(p) for p in debug_roots],'scriptOnlyRooms':[hex(r['pointer']) for r in rooms.values() if not r['identities']],'modes':dict(collections.Counter(r['mode'] for r in rooms.values())),'horizontalRooms':sum((r['width'] or 0)>1 for r in rooms.values()),'specialWithoutMap':[hex(r['pointer']) for r in rooms.values() if r['specialWithoutMap']],'errors':errors}
(ROOT/'private-v2/room-graph.json').write_text(json.dumps(list(rooms.values()),indent=2))
(ROOT/'diagnostics-v2/room-graph-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
