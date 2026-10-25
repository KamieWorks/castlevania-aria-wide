#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

// Experimental renderer only. Never installed into the game directory.
// All graphics mutations apply to the private copy, not the live PPU.
static void call_ecx_edx(uintptr_t fn, void* ppu, int y) {
    __asm {
        mov ecx, ppu
        mov edx, y
        call fn
    }
}
static void sprites(uintptr_t fn, void* ppu, int y) {
    void* output=(uint8_t*)ppu+0x20c10;
    __asm {
        mov ecx, ppu
        mov edx, y
        push output
        call fn
        add esp,4
    }
}
static int renderSnapshot(uintptr_t module, const void* source, uint16_t* output, int shift,bool objectsOnly) {
    auto p=(uint8_t*)VirtualAlloc(nullptr,0x5f4b8,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!p)return -1;
    memcpy(p,source,0x5f4b8);
    auto u16=[&](size_t o)->uint16_t& {return *(uint16_t*)(p+o);};
    auto u32=[&](size_t o)->uint32_t& {return *(uint32_t*)(p+o);};
    const int mode=u16(0x22048)&7;
    if(mode>1) {VirtualFree(p,0,MEM_RELEASE);return -2;}
    u32(0x5e064)=0;
    if(objectsOnly){
        u16(0x22048)&=~0x0f00;u16(0x21fe8)&=~0x0f00;
        u16(0x22038)=0;u32(0x5f46c)=0;
        for(int x=0;x<240;x++)for(int bg=0;bg<4;bg++)u32(0x20c00+x*20+bg*4)=0x80000000;
    }
    for(int bg=0;bg<4;bg++)u16(0x21ff8+bg*4)=(u16(0x21ff8+bg*4)+shift)&511;
    if(mode==1){
        int dx=(short)u16(0x22008)*shift,dy=(short)u16(0x2200c)*shift;
        u32(0x21fd0)+=dx;u32(0x21fd8)+=dy;
        u32(0x22010)=(u32(0x22010)+dx)&0x0fffffff;
        u32(0x22014)=(u32(0x22014)+dy)&0x0fffffff;
    }
    for(int o=0;o<128;o++) {
        auto& attr=u16(0x20002+o*8);
        attr=(attr&~511)|((attr-shift)&511);
    }
    // Window endpoints follow screen coordinates; force a mask rebuild.
    for(int w=0;w<2;w++) {
        auto& reg=u16(0x22028+w*2);
        int l=(reg>>8)==0?0:(reg>>8)-shift,r=(reg&255)==240?240:(reg&255)-shift;
        reg=((l<0?0:l>240?240:l)<<8)|(r<0?0:r>240?240:r);
    }
    u32(0x21fc8)=u32(0x21fcc)=0xffffffff;
    call_ecx_edx(module+0x43140,p,0);
    for(int y=0;y<160;y++) {
        call_ecx_edx(module+0x431c0,p,y);
        sprites(module+0x443e0,p,y);
        ((void(__cdecl*)(void*,int))(module+(mode==1?0x45810:0x45160)))(p,y);
        memcpy(output+y*240,p+0x22064+y*512,480);
    }
    VirtualFree(p,0,MEM_RELEASE);
    return 0;
}
extern "C" __declspec(dllexport) int __cdecl RenderSnapshot(uintptr_t module,const void* source,uint16_t* output,int shift){return renderSnapshot(module,source,output,shift,false);}
extern "C" __declspec(dllexport) int __cdecl RenderObjects(uintptr_t module,const void* source,uint16_t* output,int shift){return renderSnapshot(module,source,output,shift,true);}
