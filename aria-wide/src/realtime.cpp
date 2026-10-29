#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include <bcrypt.h>
#include <intrin.h>
#include "MinHook.h"
#pragma comment(lib,"bcrypt.lib")

using U8=uint8_t;using U16=uint16_t;using U32=uint32_t;
static uintptr_t image;
static U8* activeContext;
static U8* activePpu;
static U8* sides[2];
static U8* backdropPpu;
static U16 wide[288*162];
static U16 sideFrames[2][240*160];
static U32 frames,lines,unknownModes;
static bool extendedFrame;
static int cameraX,roomWidth;
static bool mainLayerBackdrop;
// Keep the optional renderer available for experimentation, disabled by default.
static bool extendFixedRooms=false;
static int viewportLeft=24;
static int backgroundCorrection[4];
static bool installed;
static volatile LONG running;
static bool hooksReady,mhReady;
static U32 contextChanges,destroyedContexts;
static U32 clearedMovieOwners,deferredHeadsFreed,protectedDestructors;
static bool exactBuild(){
    wchar_t path[32768];if(!GetModuleFileNameW(nullptr,path,32768))return false;
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    DWORD size=GetFileSize(file,nullptr),read=0;bool valid=false;
    const U8 expected[32]={0x40,0x4e,0x78,0xad,0xe8,0xb9,0x2f,0xe3,0xa8,0x9a,0xa2,0xed,0x3e,0x7d,0xe8,0xbd,0xe3,0x54,0x5d,0x69,0x4e,0x66,0x98,0x35,0xa8,0x11,0x45,0xf5,0xe0,0x26,0xe6,0xbb};
    if(size==3291736){
        U8* data=(U8*)VirtualAlloc(nullptr,size,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if(data){
            BCRYPT_ALG_HANDLE algorithm=nullptr;U8 digest[32];
            if(ReadFile(file,data,size,&read,nullptr)&&read==size&&BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0){
                valid=BCryptHash(algorithm,nullptr,0,data,size,digest,sizeof digest)>=0&&!memcmp(digest,expected,32);
                BCryptCloseAlgorithmProvider(algorithm,0);
            }
            VirtualFree(data,0,MEM_RELEASE);
        }
    }
    CloseHandle(file);return valid;
}
using Scan=void(__fastcall*)(U8*,int);
using Present=void(__fastcall*)(U8*,U8*);
using Info=void(__cdecl*)(U8*,int*);
using State=uintptr_t(__fastcall*)(U8*,void*);
using Destroy=uintptr_t(__cdecl*)(U8*);
using ThisVoid=void(__fastcall*)(U8*,void*);
static Scan originalScan;
static Present originalPresent;
static Info originalInfo;
static State originalSave,originalLoad;
static Destroy originalDestroy;
static ThisVoid originalTaskClear,originalStateFree,originalEmuDtor;
struct EndingHeads {U8* heads[2];bool deferred[2];EndingHeads* previous;};
static __declspec(thread) EndingHeads* endingHeads;
static bool warmHistory=true;
struct CloudActor {int x,y;U32 palette;};
struct CloudFrame {U32 room,count;CloudActor actors[224];};
struct CloudState {CloudFrame pending;int correction[128];};
static CloudState clouds;
// Only the two visible margins need additional history. Native center state
// remains serialized by the emulator itself. Unknown readers ignore this tag.
struct MarginState {
    U32 magic,version,expanded;
    int camera,width;
    U16 pixels[2][3][160][48];
    CloudState clouds;
};
static MarginState marginState;
static const char stateTag[]="ARIA-WIDE-1";
static void clearContext(){
    activeContext=nullptr;activePpu=nullptr;extendedFrame=false;
    cameraX=roomWidth=0;viewportLeft=24;warmHistory=false;
    memset(backgroundCorrection,0,sizeof backgroundCorrection);
    memset(&clouds,0,sizeof clouds);
}
static U16& word(U8* p,size_t off){return *(U16*)(p+off);}
static U32& dword(U8* p,size_t off){return *(U32*)(p+off);}
static const U8* guest(U32 address,size_t length){
    if(!activeContext)return nullptr;
    if(address>=0x02000000 && address<0x02040000 && length<=0x02040000-address)return activeContext+0x150+address-0x02000000;
    U32 size=dword(activeContext,0x1a055c);
    if(address>=0x08000000 && address-0x08000000<size && length<=size-(address-0x08000000))return *(U8**)(activeContext+0x1a0558)+address-0x08000000;
    return nullptr;
}
static int64_t floorRatio(int64_t value,int64_t divisor){
    int64_t q=value/divisor;return q-(value%divisor<0?1:0);
}
static void captureClouds(){
    clouds.pending.count=0;clouds.pending.room=0;
    if(!activeContext)return;
    U8* ram=activeContext+0x150;
    if(ram[0x10]!=4||ram[0x64]!=1)return;
    clouds.pending.room=dword(ram,0x88);
    for(int i=0;i<224;i++){
        U8* actor=ram+0x4e4+i*0x84;
        if(actor[0x0a]!=1||actor[0x5c]!=30||(actor[0x5a]&6)!=2)continue;
        U32 fn=dword(actor,0);if(!(fn&1))continue;
        const U8* code=guest(fn-1,0xc0);if(!code)continue;
        // Region-independent Thumb signature of the native cloud controller:
        // own drift, then subtract camera velocity / 12 on both axes. Type,
        // palette or OBJ priority alone would also match unrelated scenery.
        const U8 prologue[]={0xf0,0xb5,0x07,0x1c,0xb8,0x7a,0x00,0x28};
        const U8 drift[]={0x38,0x6d,0xb8,0x64,0x3d,0x6c,0x2d,0x18,0x3d,0x64,0x7e,0x6c,0xf8,0x6c,0x36,0x18,0x7e,0x64};
        if(memcmp(code,prologue,sizeof prologue)||memcmp(code+0x78,drift,sizeof drift)||
           *(const U16*)(code+0x94)!=0x210c||*(const U16*)(code+0xa0)!=0x210c||
           *(const U32*)(code+0xbc)!=0xa094||dword(actor,4)!=*(const U32*)(code+0xb4))continue;
        int x=(int32_t)dword(actor,0x40),y=(int32_t)dword(actor,0x44);
        if(x < -1024*65536||x > 1024*65536||y < -512*65536||y > 512*65536)continue;
        clouds.pending.actors[clouds.pending.count++]={x,y,U32((actor[0x5a]>>3)&15)};
    }
}
static void cloudState(){
    memset(clouds.correction,0,sizeof clouds.correction);
    if(roomWidth<288||(word(activePpu,0x22048)&7)!=0||
       clouds.pending.room!=dword(activeContext+0x150,0x88))return;
    for(int o=0;o<128;o++){
        U16 a0=word(activePpu,0x20000+o*8),a1=word(activePpu,0x20002+o*8),a2=word(activePpu,0x20004+o*8);
        // Native semitransparent, non-affine 32x16 cloud pieces. Birds in the
        // same palette / priority are normal OBJ and must retain world motion.
        if((a0&0xff00)!=0x4400||(a1&0xfe00)!=0x8000||(a2&0x0c00)!=0x0c00)continue;
        int correction=0;bool found=false,ambiguous=false;
        for(U32 i=0;i<clouds.pending.count;i++){
            const auto& actor=clouds.pending.actors[i];
            if(actor.palette!=U32(a2>>12)||((int(floorRatio(actor.y,65536))-8)&255)!=(a0&255))continue;
            int dx=((a1&511)-int(floorRatio(actor.x,65536)))&511;
            if(dx!=0&&dx!=496&&dx!=480)continue;
            // Round the combined native subpixel position once. Rounding a
            // uniform integer offset independently introduces edge jitter.
            int c=int(floorRatio(int64_t(actor.x)*12-int64_t(viewportLeft-24)*11*65536,12*65536)-floorRatio(actor.x,65536));
            if(found&&c!=correction)ambiguous=true;
            correction=c;found=true;
        }
        if(found&&!ambiguous)clouds.correction[o]=correction;
    }
}
static void parallaxState(){
    memset(backgroundCorrection,0,sizeof backgroundCorrection);
    if(roomWidth<288)return;
    U8* ram=activeContext+0x150;
    // Guest RAM may already describe the next frame. Anchor both viewport
    // and parallax to the camera latched for this raster, not that future one.
    int64_t metadataCamera=(int32_t)dword(ram,0xa098);
    int64_t nativeCamera=int64_t(cameraX)*65536;
    int64_t cameraLimit=int64_t(roomWidth-288)*65536;
    int64_t wideCamera=nativeCamera-24*65536;
    if(wideCamera<0)wideCamera=0;if(wideCamera>cameraLimit)wideCamera=cameraLimit;
    int64_t targetCamera=wideCamera+24*65536;
    for(int bg=2;bg<4;bg++){
        // Mode-1 BG2 has an affine camera and must retain that native path.
        if((word(activePpu,0x22048)&7)!=0)continue;
        if(word(activePpu,0x21ff0+bg*2)&0xc000)continue;
        U8* info=ram+0xa078+bg*28;
        const U8* meta=guest(dword(info,0),16);
        if(!meta||meta[0]<1||meta[0]>64||meta[1]<1||meta[1]>64)continue;
        int numerator=0,denominator=1;bool streamed=false;
        // Native horizontal camera rates. HBlank waves and time-driven
        // scrolling are left in the scanline registers, never frozen.
        switch(info[0x18]){
            case 1:case 3:case 6:case 12:case 19:case 24:case 26:case 31:case 36:
                numerator=1;streamed=true;break;
            case 2:case 4:numerator=1;denominator=2;streamed=true;break;
            case 5:case 7:numerator=2;streamed=true;break;
            case 11:case 13:case 15:case 16:case 23:
                numerator=max(0,int(word(info,0x14))-240);
                denominator=max(1,int(word(ram,0xa094+0x14))-240);
                streamed=true;break;
            case 30:numerator=1;break;
            case 0:case 8:case 9:case 10:case 14:case 17:case 20:
            case 22:case 25:case 28:case 29:case 33:case 34:case 35:break;
            default:continue; // Unknown / affine effects retain native rendering.
        }
        if(streamed&&meta[0]==1)numerator=0;
        int64_t a=floorRatio(nativeCamera*numerator,denominator);
        int64_t b=floorRatio(targetCamera*numerator,denominator);
        int64_t c=floorRatio(metadataCamera*numerator,denominator);
        if(streamed){
            int64_t limit=int64_t(meta[0]*256-240)*65536;
            if(a<0)a=0;if(a>limit)a=limit;
            if(b<0)b=0;if(b>limit)b=limit;
            if(c<0)c=0;if(c>limit)c=limit;
        }
        // Keep the layer's native fractional position / initial offset, but
        // remove the same future-camera step before rounding a pixel offset.
        int64_t position=(int32_t)dword(info,4)+a-c;
        backgroundCorrection[bg]=int(floorRatio(position+b-a+int64_t(viewportLeft-24)*65536,65536)-floorRatio(position,65536));
    }
}
static bool roomState(){
    memset(backgroundCorrection,0,sizeof backgroundCorrection);
    if(!activeContext)return false;
    U8* ram=activeContext+0x150;
    if(ram[0x10]!=4||ram[0x64]!=1)return false;
    // Illustration-only scripted scenes retain the previous BG metadata in
    // RAM. The current room header is authoritative about whether a world
    // map exists; never rebuild its margins from that stale previous map.
    const U8* header=guest(dword(ram,0x88),36);
    const U8* layer=header?guest(*(const U32*)(header+8),12):nullptr;
    if(!layer||!*(const U32*)(layer+8))return false;
    const U8* meta=guest(dword(ram,0xa094),16);
    if(!meta||meta[0]<1||meta[0]>64||meta[1]<1||meta[1]>64)return false;
    if(meta[0]==1&&!extendFixedRooms)return false;
    cameraX=(short)word(ram,0xa09a);
    roomWidth=meta[0]==1?240:meta[0]*256;
    int rasterDelta=((int(word(activePpu,0x21ffc)&511)-cameraX+256)&511)-256;
    // Normal camera updates are capped at eight pixels. Do not reinterpret
    // unrelated transition/effect register values as a different room page.
    if(rasterDelta>=-8&&rasterDelta<=8)cameraX+=rasterDelta;
    cameraX=max(0,min(roomWidth-240,cameraX));
    // Opt-in decoration only; the original arena and collision never change.
    mainLayerBackdrop=meta[0]==1;
    // Keep a 288-pixel viewport inside large rooms at either camera limit.
    // Place the native raster at 0..48 using its own latched camera phase.
    int wideCamera=max(0,min(roomWidth-288,cameraX-24));
    viewportLeft=roomWidth>=288?max(0,min(48,cameraX-wideCamera)):24;
    parallaxState();
    return roomWidth>=240;
}
static bool tileEntry(int bg,int tx,int ty,U16& entry){
    if(tx<0||ty<0)return false;
    U8* ram=activeContext+0x150;
    const U8* meta=guest(dword(ram,0xa078+bg*28),16);
    if(!meta||meta[0]<1||meta[1]<1||tx>=meta[0]*32||ty>=meta[1]*32)return false;
    auto block=guest(*(U32*)(meta+12)+((ty/4)*meta[0]*8+tx/4)*2,2);
    if(!block)return false;
    U16 b=*(U16*)block;
    if(!(b&0x3fff)){entry=0;return true;}
    int sx=tx&3,sy=ty&3;
    if(b&0x4000)sx=3-sx;
    if(b&0x8000)sy=3-sy;
    U32 table=(*(U16*)(meta+2)&2)?(0x02000000+(bg==1?0xa108:0xc0ec)):*(U32*)(meta+4);
    auto raw=guest(table+(((b&0x3fff)-1)*16+sy*4+sx)*2,2);
    if(!raw)return false;
    entry=*(U16*)raw^((b&0xc000)>>4);return true;
}
static void repairMargin(U8* ppu,int y,int shift){
    U8* ram=activeContext+0x150;
    // Repair newly exposed cells in private VRAM, including compensated
    // background columns in the central raster. Live VRAM stays intact.
    for(int bg=1;bg<4;bg++){
        if(!(word(ppu,0x22048)&(0x100<<bg)))continue;
        if(shift==0&&(bg==1||backgroundCorrection[bg]==0))continue;
        if((word(ppu,0x22048)&7)==1&&bg>=2)continue; // BG2 is affine in mode 1.
        U16 ctrl=word(ppu,0x21ff0+bg*2);
        if(ctrl&0xc000)continue; // Alternative tile layouts require separate validation.
        int camx=(short)word(ram,0xa078+bg*28+6),camy=(short)word(ram,0xa078+bg*28+10);
        int scrollx=word(ppu,0x21ff8+bg*4),scrolly=word(ppu,0x21ffa+bg*4);
        int dx=((scrollx-camx-shift+256)&511)-256;
        int dy=((scrolly-camy+256)&511)-256;
        int worldx=camx+shift+dx;
        int first=shift==0?0:(shift<0?0:192),last=shift==0?240:(shift<0?48:240);
        for(int x=first;x<last;x++){
            int wx=worldx+x,wy=camy+dy+y;
            if(wy<0)continue;
            int tx=wx>=0?wx/8:(wx-7)/8;bool reflect=false;
            if(bg==1&&mainLayerBackdrop&&(wx<0||wx>=240)){
                tx=tx<0?-tx-1:59-tx;reflect=true;
            }else if(wx<0)continue;
            U16 entry=0;if(!tileEntry(bg,tx,wy/8,entry))continue;
            if(reflect)entry^=0x400;
            int tilex=((scrollx+x)/8)&31,tiley=((scrolly+y)/8)&31;
            size_t address=(ctrl&0x1f00)*8+(tiley*32+tilex)*2;
            if(address+2<=0x10000)word(ppu,address)=entry;
        }
    }
}
static void ecxCall(uintptr_t fn,U8* p,int y){
    __asm {
        mov ecx,p
        mov edx,y
        call fn
    }
}
static void objCall(U8* p,int y){
    uintptr_t fn=image+0x443e0;U8* output=p+0x20c10;
    __asm {
        mov ecx,p
        mov edx,y
        push output
        call fn
        add esp,4
    }
}
static bool hudLayout(U8* ppu){
    // Native gameplay HUD uses BG0 character block 0 / screen block 28.
    // Portrait conversations use a different character block and stay native.
    return (word(ppu,0x21ff0)&0xfffc)==0x1c00;
}
static bool hudNumber(U8* ppu,int index){
    U16 a0=word(ppu,0x20000+index*8),a1=word(ppu,0x20002+index*8),a2=word(ppu,0x20004+index*8);
    int x=a1&511,tile=a2&1023;
    // The small native HP digits: palette 7, digit tiles 0x80..0x89,
    // 5-pixel advances from (6,6). Do not move floating damage numbers.
    return a0==6&&(a1&~511)==0&&x>=6&&x<=26&&(x-6)%5==0&&(a2&0xfc00)==0x7000&&tile>=0x80&&tile<=0x89;
}
static bool hudLeftObject(U8* ppu,int index){
    if(hudNumber(ppu,index))return true;
    U16 a0=word(ppu,0x20000+index*8),a1=word(ppu,0x20002+index*8),a2=word(ppu,0x20004+index*8);
    int palette=a2&0xfc00,tile=a2&1023;
    // Julius draws the weapon and its frame as OBJ, independently of BG0.
    // The large axe/cross start at (104,-4); small icons/frame at (112,4).
    // Match native geometry, flags, palette and tiles, never an OAM index:
    // actual projectiles and other world sprites must keep the world camera.
    if(palette!=0x2000&&palette!=0x3000)return false;
    if(a0==0xfc&&a1==0x9068)return tile==0x210||tile==0x290;
    return a0==4&&a1==0x5070&&(tile==0x296||tile==0x2d4||tile==0x2d6);
}
static void hudText(U8* ppu,int y,U32* line){
    uintptr_t fn=image+0x433a0;
    __asm {
        mov ecx,ppu
        xor edx,edx
        push line
        push y
        call fn
        add esp,8
    }
}
static int topNoticeRow(U8* ppu){
    size_t map=(word(ppu,0x21ff0)&0x1f00)*8;
    // Row 1 is the non-modal top-right notice. The first-acquisition
    // description can instead use a centered box starting at row 3.
    for(int row=1;row<=3;row+=2)for(int x=0;x<29;x++)
        if(word(ppu,map+row*64+x*2)==0xe220&&word(ppu,map+row*64+(x+1)*2)==0xe234)return row;
    return 0;
}
static bool soulNoticeTile(U8* ppu,int x,int y,U16 scroll,int firstRow){
    if(x<0||x>=240)return false;
    int row=((y+word(ppu,0x21ffa))&255)/8;
    if(row<firstRow||row>firstRow+2)return false;
    int column=((x+scroll)&255)/8;
    size_t map=(word(ppu,0x21ff0)&0x1f00)*8;
    U16 tile=word(ppu,map+(row*32+column)*2);
    // Native non-modal soul notices use palette E and the notification
    // frame/font tiles in rows 1..3, alongside the palette-D health HUD.
    return (tile&0xf000)==0xe000&&(tile&1023)>=0x220&&(tile&1023)<0x300;
}
static bool hudLine(U8* ppu,int y,int shift){
    if(!hudLayout(ppu)||!(word(ppu,0x22048)&0x100))return false;
    size_t map=(word(ppu,0x21ff0)&0x1f00)*8;
    // Item/currency notifications start at column 0 of row 18. Enemy
    // notices use the same three rows but are right aligned by the game.
    int bottomAnchor=word(ppu,map+18*64)==0xe220?0:48;
    int anchor=y<40?0:(y>=120?bottomAnchor:24);
    int delta=viewportLeft+shift-anchor;
    U16 scroll=word(ppu,0x21ff8);word(ppu,0x21ff8)=(scroll+delta)&511;
    U32* line=(U32*)(ppu+0x20c00);hudText(ppu,y,line);
    int noticeRow=y<40?topNoticeRow(ppu):0;
    if(noticeRow){
        // A row can contain BOTH the left health HUD and a right soul
        // notice. Compose their native tile pixels with separate anchors.
        static U32 rightLine[240*5];int rightDelta=viewportLeft+shift-(noticeRow==1?48:24);
        word(ppu,0x21ff8)=(scroll+rightDelta)&511;hudText(ppu,y,rightLine);
        for(int x=0;x<240;x++){
            if(x+delta<0||x+delta>=240||soulNoticeTile(ppu,x+delta,y,scroll,noticeRow))line[x*5]=0x80000000;
            if(soulNoticeTile(ppu,x+rightDelta,y,scroll,noticeRow))line[x*5]=rightLine[x*5];
        }
    }
    word(ppu,0x21ff8)=scroll;
    // BG0 is a 256-pixel hardware map. Its native 240-pixel UI must not
    // repeat into the extra 48 pixels when that hardware map wraps.
    if(!noticeRow)for(int x=0;x<240;x++)if(x+delta<0||x+delta>=240)line[x*5]=0x80000000;
    // The native compositor consumes the prepared BG0 line even when its
    // redraw bit is off; window and blend masks remain unchanged.
    word(ppu,0x22048)&=~0x100;
    return true;
}
static bool identify(U8* context){
    if(!context)return false;
    U8* rom=*(U8**)(context+0x1a0558);
    U32 size=dword(context,0x1a055c);
    if(!rom||size<0x100||size>0x2000000)return false;
    // Verify exact Aria game code independently of language selection.
    if(memcmp(rom+0xac,"A2C",3)!=0)return false;
    U8* ppu=*(U8**)(context+0x138);if(!ppu)return false;
    if(context!=activeContext||ppu!=activePpu){
        extendedFrame=false;warmHistory=false;cameraX=roomWidth=0;contextChanges++;
        for(auto side:sides)if(side)memset(side,0,0x5f4b8);
    }
    activeContext=context;activePpu=ppu;return true;
}
static void __cdecl infoHook(U8* context,int* out){
    originalInfo(context,out);
    if(!running||!out)return;
    if(identify(context)){
        out[0]=288;out[1]=162;out[3]=288;out[4]=162;out[5]=1;out[6]=out[7]=0;
    }else clearContext();
}
static void shifted(U8* live,U8* copy,int y,int shift,bool backgroundOnly=false){
    memcpy(copy,live,0x22064);
    memcpy(copy+0x5e064,live+0x5e064,0x5f4a8-0x5e064);
    bool anchoredHud=hudLayout(live);
    if(!hudLine(copy,y,shift)&&shift!=0){
        word(copy,0x22048)&=~0x100;
        for(int x=0;x<240;x++)dword(copy,0x20c00+x*20)=0x80000000;
    }
    if(backgroundOnly&&!mainLayerBackdrop){
        // BG1 is the collision-bearing room layer. Beyond its original bounds
        // show only the existing background layers and offscreen objects.
        // No room dimensions, collision data, entity coordinates or ROM change.
        word(copy,0x22048)&=~0x200;word(copy,0x21fe8)&=~0x200;
        for(int x=0;x<240;x++)dword(copy,0x20c04+x*20)=0x80000000;
    }
    for(int bg=1;bg<4;bg++)word(copy,0x21ff8+bg*4)=(word(copy,0x21ff8+bg*4)+shift+backgroundCorrection[bg])&511;
    int mode=word(copy,0x22048)&7;
    if(mode==1){
        // Shift both reload registers and running affine coordinates. The
        // native renderer chooses between them independently for X and Y.
        int dx=(short)word(copy,0x22008)*shift,dy=(short)word(copy,0x2200c)*shift;
        dword(copy,0x21fd0)+=dx;dword(copy,0x21fd8)+=dy;
        dword(copy,0x22010)=(dword(copy,0x22010)+dx)&0x0fffffff;
        dword(copy,0x22014)=(dword(copy,0x22014)+dy)&0x0fffffff;
    }
    repairMargin(copy,y,shift);
    for(int o=0;shift!=0&&o<128;o++){
        // Aria hides unused OAM entries at x=-32 instead of setting OBJ
        // disable. The wider left margin must not reveal their tile zero.
        // Match the engine's exact blank tuple; keep affine parameter words.
        if(word(copy,0x20000+o*8)==0&&word(copy,0x20002+o*8)==0x1e0&&word(copy,0x20004+o*8)==0){
            word(copy,0x20000+o*8)=0x200;continue;
        }
        bool leftHud=anchoredHud&&hudLeftObject(copy,o);
        auto& a=word(copy,0x20002+o*8);a=(a&~511)|((a-shift-(leftHud?viewportLeft:0)+clouds.correction[o])&511);
    }
    for(int w=0;w<2;w++){
        auto& a=word(copy,0x22028+w*2);int oldLeft=a>>8,oldRight=a&255;
        int l=oldLeft==0?0:oldLeft-shift,r=oldRight==240?240:oldRight-shift;
        a=(U16)((max(0,min(240,l))<<8)|max(0,min(240,r)));
    }
    dword(copy,0x21fc8)=dword(copy,0x21fcc)=0xffffffff;
    ecxCall(image+0x43140,copy,y);
    // A central clone inherits the native precomputed current OBJ line.
    // The live scan call must still prepare y+1 with its original pipeline.
    if(shift!=0)objCall(copy,y);
    ((void(__cdecl*)(U8*,int))(image+(mode==1?0x45810:0x45160)))(copy,y);
}
static void __fastcall scanHook(U8* ppu,int y){
    if(!running){originalScan(ppu,y);return;}
    if(ppu==activePpu&&y==0){
        bool next=roomState();if(next&&!extendedFrame)warmHistory=false;extendedFrame=next;
        memset(clouds.correction,0,sizeof clouds.correction);if(next)cloudState();
    }
    bool visible=ppu==activePpu&&y>=0&&y<160&&dword(ppu,0x22058);
    bool blank=(word(ppu,0x22054)&128)!=0;
    bool render=visible&&!blank;
    int mode=word(ppu,0x22048)&7;
    bool correctedCenter=render&&extendedFrame&&mode==0&&(backgroundCorrection[2]||backgroundCorrection[3]);
    if(render&&mode<=1&&extendedFrame){
        for(int side=0;side<2;side++){
            int shift=side?48:-48,first=side?192:0;
            int worldStart=cameraX+shift+first;
            bool outside=worldStart<0||worldStart+48>roomWidth;
            bool allOutside=worldStart+48<=0||worldStart>=roomWidth;
            shifted(ppu,sides[side],y,shift,allOutside);
            if(outside&&!allOutside){
                shifted(ppu,backdropPpu,y,shift,true);
                U32 index=dword(ppu,0x5e064);size_t row=0x22064+index*0x14000+y*512;
                for(int x=first;x<first+48;x++)if(cameraX+shift+x<0||cameraX+shift+x>=roomWidth)
                    word(sides[side],row+x*2)=word(backdropPpu,row+x*2);
            }
        }
        if(correctedCenter)shifted(ppu,backdropPpu,y,0);
        lines++;
    }
    else if(render&&mode>1)unknownModes++;
    if(visible&&blank&&extendedFrame&&mode<=1){
        for(auto side:sides){
            dword(side,0x5e064)=dword(ppu,0x5e064);
            memset(side+0x22064+dword(ppu,0x5e064)*0x14000+y*512,0xff,480);
        }
    }
    if(render&&extendedFrame&&mode<=1){
        // Only cached PPU render state is adjusted, synchronously around the
        // native raster call. Restore OAM/flags before guest execution resumes.
        U16 flags=word(ppu,0x22048),savedX[128];bool moved[128]={};
        bool anchoredHud=hudLayout(ppu);
        for(int o=0;o<128;o++){
            int dx=clouds.correction[o]-(anchoredHud&&hudLeftObject(ppu,o)?viewportLeft:0);if(!dx)continue;
            moved[o]=true;savedX[o]=word(ppu,0x20002+o*8);
            word(ppu,0x20002+o*8)=(savedX[o]&~511)|((savedX[o]+dx)&511);
        }
        if(anchoredHud)hudLine(ppu,y,0);originalScan(ppu,y);word(ppu,0x22048)=flags;
        for(int o=0;o<128;o++)if(moved[o])word(ppu,0x20002+o*8)=savedX[o];
    }else originalScan(ppu,y);
    if(correctedCenter){
        size_t row=0x22064+dword(ppu,0x5e064)*0x14000+y*512;
        memcpy(ppu+row,backdropPpu+row,480);
    }
}
static void __fastcall presentHook(U8* ppu,U8* bitmap){
    // VBlank presentation precedes guest OAM DMA. These entity fractions
    // belong to the next visible OAM frame, unlike potentially newer scan-0 RAM.
    if(running&&ppu==activePpu)captureClouds();
    if(!running||ppu!=activePpu||!dword(ppu,0x22058)||dword(ppu,0x22050)){
        originalPresent(ppu,bitmap);return;
    }
    // Private expanded frame, preserving the original central pixels.
    U8 left[0x54],right[0x54],center[0x54];
    memcpy(left,bitmap,sizeof left);memcpy(right,bitmap,sizeof right);memcpy(center,bitmap,sizeof center);
    int leftWidth=extendedFrame?viewportLeft:24,rightWidth=48-leftWidth;
    dword(left,0x1c)=dword(right,0x1c)=240*2;dword(center,0x1c)=288*2;
    *(U8**)(left+0x38)=(U8*)sideFrames[0];
    *(U8**)(right+0x38)=(U8*)sideFrames[1];
    *(U8**)(center+0x38)=(U8*)(wide+288+leftWidth);
    memset(wide,0,sizeof wide);
    if(extendedFrame&&!warmHistory){
        U32 current=dword(ppu,0x5e064);
        for(int side=0;side<2;side++)for(U32 frame=0;frame<3;frame++)if(frame!=current)
            memcpy(sides[side]+0x22064+frame*0x14000,sides[side]+0x22064+current*0x14000,0x14000);
        warmHistory=true;
    }
    if(extendedFrame&&(word(ppu,0x22048)&7)<=1){originalPresent(sides[0],left);originalPresent(sides[1],right);}
    originalPresent(ppu,center);
    if(extendedFrame&&(word(ppu,0x22048)&7)<=1)for(int y=0;y<160;y++){
        memcpy(wide+(y+1)*288,sideFrames[0]+y*240+48-leftWidth,leftWidth*2);
        memcpy(wide+(y+1)*288+leftWidth+240,sideFrames[1]+y*240+192,rightWidth*2);
    }
    // Copy only when wrapper allocated the expanded surface (getVideoInfo hook).
    if(dword(bitmap,0x1c)>=576){
        U8* out=*(U8**)(bitmap+0x34);
        for(int y=0;y<162;y++)memcpy(out+y*dword(bitmap,0x1c),wide+y*288,576);
    }else{
        U8* out=*(U8**)(bitmap+0x38);
        for(int y=0;y<160;y++)memcpy(out+y*dword(bitmap,0x1c),wide+(y+1)*288+leftWidth,480);
    }
    frames++;
}
static void stateWrite(void* head,const void* data,U32 byteCount){
    uintptr_t fn=image+0x38f50;const char* tag=stateTag;
    __asm {
        mov ecx,head
        mov edx,tag
        push byteCount
        push data
        call fn
        add esp,8
    }
}
static const MarginState* stateRead(void* head,U32* outCount){
    uintptr_t fn=image+0x38e60;const char* tag=stateTag;const MarginState* result;
    __asm {
        mov ecx,head
        mov edx,tag
        push outCount
        call fn
        add esp,4
        mov result,eax
    }
    return result;
}
static uintptr_t __fastcall saveHook(U8* context,void* unused){
    uintptr_t result=originalSave(context,unused);
    if(!running||context!=activeContext||*(U32*)(image+0x2839b4))return result;
    if(!identify(context)){clearContext();return result;}
    void* head=*(void**)(image+0x149efa4);if(!head)return result;
    marginState.magic=0x31495741;marginState.version=9;
    marginState.clouds=clouds;
    marginState.expanded=extendedFrame?1:0;marginState.camera=cameraX;marginState.width=roomWidth;
    for(int side=0;side<2;side++)for(int frame=0;frame<3;frame++)for(int y=0;y<160;y++)
        memcpy(marginState.pixels[side][frame][y],sides[side]+0x22064+frame*0x14000+y*512+(side?192:0)*2,96);
    stateWrite(head,&marginState,sizeof marginState);
    return result;
}
static uintptr_t __fastcall loadHook(U8* context,void* unused){
    uintptr_t result=originalLoad(context,unused);
    if(!running||context!=activeContext||*(U32*)(image+0x2839b4))return result;
    if(!identify(context)){clearContext();return result;}
    for(auto side:sides)memcpy(side,activePpu,0x5f4b8);
    void* head=*(void**)(image+0x149efa4);U32 size=0;
    const MarginState* saved=head?stateRead(head,&size):nullptr;
    memset(&clouds,0,sizeof clouds);
    if(saved&&size==sizeof(MarginState)&&saved->magic==0x31495741&&saved->version==9&&saved->clouds.pending.count<=224&&saved->expanded<=1&&saved->width>=0&&saved->width<=64*256&&saved->camera>=-256&&saved->camera<=64*256){
        clouds=saved->clouds;
        cameraX=saved->camera;roomWidth=saved->width;
        extendedFrame=saved->expanded!=0&&(extendFixedRooms||roomWidth>=288);
        viewportLeft=roomWidth>=288?max(0,min(48,cameraX-max(0,min(roomWidth-288,cameraX-24)))):24;
        parallaxState();
        for(int side=0;side<2;side++)for(int frame=0;frame<3;frame++)for(int y=0;y<160;y++)
            memcpy(sides[side]+0x22064+frame*0x14000+y*512+(side?192:0)*2,saved->pixels[side][frame][y],96);
        warmHistory=extendedFrame;
    }else{extendedFrame=false;warmHistory=false;}
    return result;
}
static uintptr_t __cdecl destroyHook(U8* context){
    // Invalidate before the emulator frees the PPU or reuses the allocation for
    // another game. Its own shutdown still joins any native worker threads.
    if(context==activeContext){clearContext();destroyedContexts++;}
    return originalDestroy(context);
}
static void __fastcall taskClearHook(U8* list,void* unused){
    // MovieStreamSoundPlayer owns its child through this task list as well as
    // +0x48. The native destructor destroys the list, then deletes that child
    // again. Invalidate the alias only when this list actually owns the child.
    U8* field=nullptr;U8* child=nullptr;
    if(running&&(uintptr_t)_ReturnAddress()==image+0x38642){
        field=list+0x1c;child=*(U8**)field;U8* node=*(U8**)(list+0x10);bool owned=false;
        // Intrusive MTask list: each node is the task itself, not task* storage.
        for(int n=0;node&&n<4096;n++,node=*(U8**)(node+4))if(node==child){owned=true;break;}
        if(!owned)field=nullptr;
    }
    originalTaskClear(list,unused);
    if(field&&*(U8**)field==child){*(U8**)field=nullptr;clearedMovieOwners++;}
}
static void __fastcall stateFreeHook(U8* head,void* unused){
    uintptr_t caller=(uintptr_t)_ReturnAddress();EndingHeads* job=endingHeads;
    if(running&&job)for(int i=0;i<2;i++)if(head==job->heads[i]&&caller==image+(i?0xe606:0xe5f7)){
        // Native EmuTask::~ clears these lists again later. Release all records
        // now, but keep the empty head valid until its destructor finishes.
        ((ThisVoid)(image+0x38c80))(head,nullptr);job->deferred[i]=true;return;
    }
    originalStateFree(head,unused);
}
static void __fastcall emuDtorHook(U8* parent,void* unused){
    if(!running){originalEmuDtor(parent,unused);return;}
    EndingHeads job={{*(U8**)(parent+0x168),*(U8**)(parent+0x16c)},{false,false},endingHeads};
    endingHeads=&job;originalEmuDtor(parent,unused);endingHeads=job.previous;
    for(int i=0;i<2;i++)if(job.deferred[i]&&!(i&&job.deferred[0]&&job.heads[0]==job.heads[i])){
        ((void(__cdecl*)(void*))(image+0x1ec696))(job.heads[i]);deferredHeadsFreed++;
    }
    protectedDestructors++;
}
static int abandonSetup(int code){
    // This path is used only before enabling any detour. No thread can be
    // executing our trampoline, so both hook and render allocations can go.
    if(mhReady){MH_Uninitialize();mhReady=false;}
    hooksReady=false;clearContext();
    for(auto& side:sides)if(side){VirtualFree(side,0,MEM_RELEASE);side=nullptr;}
    if(backdropPpu){VirtualFree(backdropPpu,0,MEM_RELEASE);backdropPpu=nullptr;}
    return code;
}
#ifndef ARIA_FAIL_STAGE
#define ARIA_FAIL_STAGE 0
#endif
extern "C" __declspec(dllexport) int __cdecl Install(U8* context){
    if(installed)return 0;
    if(hooksReady){
        if(context&&!identify(context))return -4;
        auto s=MH_EnableHook(MH_ALL_HOOKS);if(s!=MH_OK)return 500+s;
        installed=true;InterlockedExchange(&running,1);return 0;
    }
    if(!exactBuild())return -10;
    wchar_t configPath[32768];
    if(GetModuleFileNameW(nullptr,configPath,32768)){
        wchar_t* slash=wcsrchr(configPath,L'\\');
        if(slash){lstrcpyW(slash+1,L"AriaWide.ini");extendFixedRooms=GetPrivateProfileIntW(L"AriaWide",L"ExtendFixedRooms",0,configPath)!=0;}
    }
    image=(uintptr_t)GetModuleHandleW(nullptr);
    if(*(U16*)(image)!=0x5a4d)return -1;
    // Verify every exact-build entry before any code mutation.
    const U8 scanSig[]={0x56,0x8b,0xf1,0x57,0x8b,0xfa};
    const U8 presentSig[]={0x83,0xec,0x2c,0x8b,0x42,0x38};
    const U8 infoSig[]={0x8b,0x54,0x24,0x08,0x85,0xd2};
    const U8 saveSig[]={0x55,0x8b,0xec,0x83,0xe4,0xf8};
    const U8 loadSig[]={0x55,0x8b,0xec,0x83,0xe4,0xf8};
    const U8 taskClearSig[]={0x51,0x53,0x55,0x56,0x57};
    const U8 stateFreeSig[]={0x55,0x8b,0xe9};
    const U8 emuDtorSig[]={0x55,0x8b,0xec,0x6a,0xff};
    if(memcmp((void*)(image+0x47680),scanSig,sizeof scanSig)||memcmp((void*)(image+0x47710),presentSig,sizeof presentSig)||memcmp((void*)(image+0x39ab0),infoSig,sizeof infoSig))return -2;
    if(memcmp((void*)(image+0x406c0),saveSig,sizeof saveSig)||memcmp((void*)(image+0x40610),loadSig,sizeof loadSig))return -5;
    if(memcmp((void*)(image+0x153e80),taskClearSig,sizeof taskClearSig)||memcmp((void*)(image+0x38c20),stateFreeSig,sizeof stateFreeSig)||memcmp((void*)(image+0xe570),emuDtorSig,sizeof emuDtorSig))return -8;
    U8* destroy=(U8*)(image+0x39f60);
    if(destroy[0]!=0x83||destroy[1]!=0x3d||*(U32*)(destroy+2)!=image+0x1285480||destroy[6]!=0)return -6;
    if(context&&!identify(context))return -4;
    for(auto& side:sides){side=(U8*)VirtualAlloc(nullptr,0x5f4b8,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!side)return abandonSetup(-3);}
    backdropPpu=(U8*)VirtualAlloc(nullptr,0x5f4b8,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!backdropPpu)return abandonSetup(-3);
    if(ARIA_FAIL_STAGE==1)return abandonSetup(-101);
    auto status=MH_Initialize();if(status!=MH_OK)return abandonSetup(100+status);mhReady=true;
    status=MH_CreateHook((void*)(image+0x47680),scanHook,(void**)&originalScan);if(status!=MH_OK)return abandonSetup(200+status);
    if(ARIA_FAIL_STAGE==2)return abandonSetup(-102);
    status=MH_CreateHook((void*)(image+0x47710),presentHook,(void**)&originalPresent);if(status!=MH_OK)return abandonSetup(300+status);
    status=MH_CreateHook((void*)(image+0x39ab0),infoHook,(void**)&originalInfo);if(status!=MH_OK)return abandonSetup(400+status);
    status=MH_CreateHook((void*)(image+0x406c0),saveHook,(void**)&originalSave);if(status!=MH_OK)return abandonSetup(600+status);
    status=MH_CreateHook((void*)(image+0x40610),loadHook,(void**)&originalLoad);if(status!=MH_OK)return abandonSetup(700+status);
    status=MH_CreateHook((void*)(image+0x39f60),destroyHook,(void**)&originalDestroy);if(status!=MH_OK)return abandonSetup(800+status);
    status=MH_CreateHook((void*)(image+0x153e80),taskClearHook,(void**)&originalTaskClear);if(status!=MH_OK)return abandonSetup(900+status);
    status=MH_CreateHook((void*)(image+0x38c20),stateFreeHook,(void**)&originalStateFree);if(status!=MH_OK)return abandonSetup(1000+status);
    status=MH_CreateHook((void*)(image+0xe570),emuDtorHook,(void**)&originalEmuDtor);if(status!=MH_OK)return abandonSetup(1100+status);
    if(ARIA_FAIL_STAGE==3)return abandonSetup(-103);
    // Enabled detours must remain backed by resident code even if a consumer
    // releases its LoadLibrary handle. DllMain itself remains work-free.
    HMODULE self=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)&exactBuild,&self))return abandonSetup(-7);
    hooksReady=true;
    status=MH_EnableHook(MH_ALL_HOOKS);
    if(status!=MH_OK){
        // All detours still forward to the originals while running==0. Keep
        // trampolines resident after an enable attempt; a thread may use one.
        MH_DisableHook(MH_ALL_HOOKS);return 500+status;
    }
    installed=true;InterlockedExchange(&running,1);return 0;
}
extern "C" __declspec(dllexport) int __cdecl Uninstall(){
    if(!installed)return 0;
    InterlockedExchange(&running,0);
    auto s=MH_DisableHook(MH_ALL_HOOKS);if(s!=MH_OK){InterlockedExchange(&running,1);return s;}
    installed=false;
    // Buffers retained until process exit, avoiding freeing memory used by an in-flight frame.
    return 0;
}
extern "C" __declspec(dllexport) const U16* __cdecl GetFrame(){return wide;}
extern "C" __declspec(dllexport) int __cdecl IsInstalled(){return installed?1:0;}
extern "C" __declspec(dllexport) void __cdecl GetCounters(U32* out){out[0]=frames;out[1]=lines;out[2]=unknownModes;}
extern "C" __declspec(dllexport) void __cdecl GetViewport(U32* out){out[0]=viewportLeft;out[1]=cameraX;out[2]=roomWidth;out[3]=extendedFrame?1:0;}
extern "C" __declspec(dllexport) void __cdecl GetBackgroundCorrections(int* out){memcpy(out,backgroundCorrection,sizeof backgroundCorrection);}
extern "C" __declspec(dllexport) void __cdecl GetCloudCorrections(int* out){memcpy(out,clouds.correction,sizeof clouds.correction);}
extern "C" __declspec(dllexport) void __cdecl GetShutdownCounters(U32* out){out[0]=clearedMovieOwners;out[1]=deferredHeadsFreed;out[2]=protectedDestructors;}
extern "C" __declspec(dllexport) void __cdecl GetLifecycle(U32* out){
    out[0]=contextChanges;out[1]=destroyedContexts;out[2]=(U32)activeContext;
    out[3]=(U32)activePpu;out[4]=(U32)running;out[5]=hooksReady?1:0;
}
