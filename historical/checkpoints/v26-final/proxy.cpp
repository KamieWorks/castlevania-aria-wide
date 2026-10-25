#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#pragma comment(lib,"user32.lib")
extern "C" int __cdecl Install(uint8_t*);
static INIT_ONCE once=INIT_ONCE_STATIC_INIT;
static void* (WINAPI* realCreate)(UINT);
static BOOL CALLBACK initialize(PINIT_ONCE,PVOID,PVOID*){
    wchar_t path[MAX_PATH];UINT length=GetSystemDirectoryW(path,MAX_PATH);
    if(!length||length+11>=MAX_PATH)return FALSE;
    lstrcatW(path,L"\\d3d9.dll");
    HMODULE module=LoadLibraryW(path);
    if(!module)return FALSE;
    realCreate=(decltype(realCreate))GetProcAddress(module,"Direct3DCreate9");
    if(!realCreate)return FALSE;
    int result=Install(nullptr);
    wchar_t logPath[32768];
    if(GetModuleFileNameW(nullptr,logPath,32768)){
        wchar_t* slash=wcsrchr(logPath,L'\\');if(slash){lstrcpyW(slash+1,L"aria-wide-test.log");
            HANDLE log=CreateFileW(logPath,FILE_APPEND_DATA,FILE_SHARE_READ,nullptr,OPEN_ALWAYS,0,nullptr);
            if(log!=INVALID_HANDLE_VALUE){char line[128];DWORD written;int count=wsprintfA(line,"v26 install=%d pid=%lu\r\n",result,GetCurrentProcessId());WriteFile(log,line,count,&written,nullptr);CloseHandle(log);}
        }
    }
    return TRUE;
}
extern "C" void* WINAPI ProxyDirect3DCreate9(UINT sdk){
    if(!InitOnceExecuteOnce(&once,initialize,nullptr,nullptr)||!realCreate)return nullptr;
    return realCreate(sdk);
}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){
    if(reason==DLL_PROCESS_ATTACH)DisableThreadLibraryCalls(instance);
    return TRUE;
}



