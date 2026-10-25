#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>

int wmain(int argc,wchar_t** argv){
    if(argc!=2)return 2;
    HMODULE library=LoadLibraryW(argv[1]);if(!library)return 3;
    auto install=(int(__cdecl*)(void*))GetProcAddress(library,"Install");
    auto installed=(int(__cdecl*)())GetProcAddress(library,"IsInstalled");
    auto uninstall=(int(__cdecl*)())GetProcAddress(library,"Uninstall");
    auto create=(IDirect3D9*(WINAPI*)(UINT))GetProcAddress(library,"Direct3DCreate9");
    if(!install||!installed||!uninstall||!create)return 4;
    // This harness is deliberately not game.exe. It must be rejected before
    // any game-address access, while ordinary system D3D9 remains available.
    if(installed()!=0||install(nullptr)!=-10||installed()!=0)return 5;
    IDirect3D9* d3d=create(D3D_SDK_VERSION);if(!d3d)return 6;
    d3d->Release();Sleep(100);
    if(installed()!=0||uninstall()!=0)return 7;
    puts("Unknown executable rejected; system Direct3D9 forwarding passed.");
    FreeLibrary(library);return 0;
}
