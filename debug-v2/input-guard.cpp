// Diagnostic only: process-local GBA input isolation. Never ship with players.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "MinHook.h"
static void* original;
static volatile LONG installed,maskValue,deadline,calls,forced;
static __declspec(noinline) void __cdecl updatePad(unsigned char* context){
    DWORD now=GetTickCount(),mask=(DWORD)maskValue;
    if((LONG)((DWORD)deadline-now)<=0)mask=0;
    unsigned char* pad=*(unsigned char**)(context+12);
    *(DWORD*)(pad+0x4c4)=1023&~mask;
    InterlockedIncrement(&calls);if(mask)InterlockedIncrement(&forced);
}
static __declspec(naked) void padThunk(){
    __asm {
        pushfd
        pushad
        mov ebx,esp
        sub esp,0x210
        and esp,-16
        fxsave [esp]
        push esi
        call updatePad
        add esp,4
        fxrstor [esp]
        mov esp,ebx
        popad
        popfd
        jmp dword ptr [original]
    }
}
extern "C" __declspec(dllexport) int __cdecl InstallDebugInput(){
    if(installed)return 0;
    uintptr_t image=(uintptr_t)GetModuleHandleW(nullptr);unsigned char* p=(unsigned char*)(image+0x39b3a);
    if(p[0]!=0x83||p[1]!=0x3d||*(DWORD*)(p+2)!=image+0x283868||p[6]!=0)return -1;
    auto s=MH_Initialize();if(s!=MH_OK)return 100+s;
    s=MH_CreateHook(p,padThunk,&original);if(s!=MH_OK){MH_Uninitialize();return 200+s;}
    HMODULE self=nullptr;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,(LPCWSTR)&InstallDebugInput,&self)){MH_Uninitialize();return -2;}
    s=MH_EnableHook(p);if(s!=MH_OK)return 300+s;
    InterlockedExchange(&installed,1);return 0;
}
extern "C" __declspec(dllexport) int __cdecl SetPadPulse(DWORD mask,DWORD ms){
    if(mask>1023||ms>3000||(!ms&&mask))return -1;
    InterlockedExchange(&deadline,(LONG)(GetTickCount()+ms));InterlockedExchange(&maskValue,(LONG)mask);return 0;
}
extern "C" __declspec(dllexport) void __cdecl GetPadCounters(DWORD* out){out[0]=(DWORD)calls;out[1]=(DWORD)forced;out[2]=(DWORD)installed;}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(instance);return TRUE;}
