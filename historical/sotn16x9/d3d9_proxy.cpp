#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9types.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <cmath>

#pragma comment(lib, "user32.lib")
struct IDirect3D9;
using Direct3DCreate9Fn = void* (WINAPI*)(UINT);
using CreateDeviceFn = HRESULT (WINAPI*)(void*, UINT, D3DDEVTYPE, HWND, DWORD, void*, void**);
using SetTransformFn = HRESULT (WINAPI*)(void*, DWORD, const float*);
static CreateDeviceFn g_realCreateDevice = nullptr;
static SetTransformFn g_realSetTransform = nullptr;
static bool g_transformLogged = false;
static constexpr float kExpandX = 0.84375f;
static HMODULE g_realD3D9 = nullptr;
static Direct3DCreate9Fn g_realCreate9 = nullptr;
static BYTE* g_trampoline = nullptr;
static BYTE* g_layoutTrampoline = nullptr;
static CRITICAL_SECTION g_logLock;
static bool g_logReady = false;
static bool g_expand = true;
static int g_heightOverride = 0;
static int g_widthOverride = 0;


static void Log(const char* fmt, ...);
static HRESULT WINAPI HookSetTransform(void* device, DWORD state, const float* matrix);
static HRESULT WINAPI HookCreateDevice(void* self, UINT adapter, D3DDEVTYPE type, HWND hwnd, DWORD flags, void* pp, void** outDevice);

static void PatchDeviceVtable(void* device) {
    if (!device) return;
    void** oldVt = *reinterpret_cast<void***>(device);
    if (!oldVt) return;
    void** vt = reinterpret_cast<void**>(VirtualAlloc(nullptr, 128 * sizeof(void*), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!vt) return;
    memcpy(vt, oldVt, 128 * sizeof(void*));
    g_realSetTransform = reinterpret_cast<SetTransformFn>(vt[44]);
    vt[44] = reinterpret_cast<void*>(&HookSetTransform);
    DWORD protect = 0; VirtualProtect(device, sizeof(void*), PAGE_READWRITE, &protect);
    *reinterpret_cast<void***>(device) = vt;
    VirtualProtect(device, sizeof(void*), protect, &protect);
    Log("patched device vtable=%p SetTransform=%p", vt, g_realSetTransform);
}

static HRESULT WINAPI HookCreateDevice(void* self, UINT adapter, D3DDEVTYPE type, HWND hwnd, DWORD flags, void* pp, void** outDevice) {
    HRESULT hr = g_realCreateDevice ? g_realCreateDevice(self, adapter, type, hwnd, flags, pp, outDevice) : E_FAIL;
    if (SUCCEEDED(hr) && outDevice && *outDevice) PatchDeviceVtable(*outDevice);
    return hr;
}

static void PatchD3D9Vtable(void* obj) {
    if (!obj) return;
    void** oldVt = *reinterpret_cast<void***>(obj);
    if (!oldVt) return;
    void** vt = reinterpret_cast<void**>(VirtualAlloc(nullptr, 20 * sizeof(void*), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!vt) return;
    memcpy(vt, oldVt, 20 * sizeof(void*));
    g_realCreateDevice = reinterpret_cast<CreateDeviceFn>(vt[16]);
    vt[16] = reinterpret_cast<void*>(&HookCreateDevice);
    DWORD protect = 0; VirtualProtect(obj, sizeof(void*), PAGE_READWRITE, &protect);
    *reinterpret_cast<void***>(obj) = vt;
    VirtualProtect(obj, sizeof(void*), protect, &protect);
    Log("patched D3D9 vtable=%p CreateDevice=%p", vt, g_realCreateDevice);
}

static HRESULT WINAPI HookSetTransform(void* device, DWORD state, const float* matrix) {
    if (state == D3DTS_PROJECTION && matrix && g_expand && g_realSetTransform) {
        float m[16]; memcpy(m, matrix, sizeof(m));
        float denom = std::fabs(m[5]);
        float ratio = denom > 1e-6f ? std::fabs(m[0]) / denom : 0.0f;
        if (ratio > 0.58f && ratio < 0.74f) {
            m[0] *= kExpandX;
            if (!g_transformLogged) { Log("expanded projection m00=%f m11=%f ratio=%f", matrix[0], matrix[5], ratio); g_transformLogged = true; }
            return g_realSetTransform(device, state, m);
        }
    }
    return g_realSetTransform ? g_realSetTransform(device, state, matrix) : E_FAIL;
}

static void Log(const char* fmt, ...) {
    if (!g_logReady) return;
    EnterCriticalSection(&g_logLock);
    char path[MAX_PATH] = {};
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    char* slash = strrchr(path, '\\');
    if (slash) slash[1] = 0;
    strcat_s(path, "sotn16x9.log");
    FILE* f = nullptr;
    fopen_s(&f, path, "ab");
    if (f) {
        SYSTEMTIME st{}; GetLocalTime(&st);
        fprintf(f, "[%02u:%02u:%02u.%03u] ", st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
        va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
        fputc('\n', f); fclose(f);
    }
    LeaveCriticalSection(&g_logLock);
}
static void ReadConfig() {
    char path[MAX_PATH] = {};
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    char* slash = strrchr(path, '\\'); if (slash) slash[1] = 0;
    strcat_s(path, "sotn16x9.ini");
    g_expand = GetPrivateProfileIntA("sotn16x9", "ExpandLogicalView", 1, path) != 0;
    g_heightOverride = GetPrivateProfileIntA("sotn16x9", "Height", 0, path);
    g_widthOverride = GetPrivateProfileIntA("sotn16x9", "Width", 0, path);
}
static bool IsPlausibleGbaSize(int w, int h) {
    if (w <= 0 || h <= 0 || w > 2048 || h > 2048) return false;
    return std::fabs(static_cast<double>(w) / static_cast<double>(h) - 1.5) < 0.03;
}
static void __cdecl OnLayoutArgs(int* width, int* height) {
    if (!width || !height) return;
    __try {
        int oldW = *width, oldH = *height, newW = oldW, newH = oldH;
        if (g_expand && IsPlausibleGbaSize(oldW, oldH)) {
            newH = g_heightOverride > 0 ? g_heightOverride : oldH;
            newW = g_widthOverride > 0 ? g_widthOverride : static_cast<int>(std::lround(newH * (16.0 / 9.0)));
            if (newW < oldW) newW = oldW;
            *width = newW;
            *height = newH;
        }
        Log("layout %dx%d -> %dx%d expand=%d", oldW, oldH, newW, newH, g_expand ? 1 : 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log("layout argument probe failed");
    }
}

static void __cdecl OnInit(void* self) {
    if (!self) return;
    __try {
        volatile int* w = reinterpret_cast<volatile int*>(reinterpret_cast<uintptr_t>(self) + 0x3b0);
        volatile int* h = reinterpret_cast<volatile int*>(reinterpret_cast<uintptr_t>(self) + 0x3b4);
        int oldW = *w, oldH = *h, newW = oldW, newH = oldH;
        if (g_expand && IsPlausibleGbaSize(oldW, oldH)) {
            newH = g_heightOverride > 0 ? g_heightOverride : oldH;
            newW = g_widthOverride > 0 ? g_widthOverride : static_cast<int>(std::lround(newH * (16.0 / 9.0)));
            if (newW < oldW) newW = oldW;
            *w = newW; *h = newH;
        }
        Log("init this=%p logical=%dx%d -> %dx%d expand=%d", self, oldW, oldH, newW, newH, g_expand ? 1 : 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) { Log("init this=%p memory probe failed", self); }
}
extern "C" __declspec(naked) void HookLayout() {
    __asm {
        pushad
        lea eax, [esp + 0x24]
        lea edx, [esp + 0x28]
        push edx
        push eax
        call OnLayoutArgs
        add esp, 8
        popad
        jmp dword ptr [g_layoutTrampoline]
    }
}

extern "C" __declspec(naked) void HookInit() {
    __asm {
        pushad
        mov eax, ecx
        push eax
        call OnInit
        add esp, 4
        popad
        jmp dword ptr [g_trampoline]
    }
}
static bool PatchInit() {
    HMODULE game = GetModuleHandleA("game.exe"); if (!game) return false;
    BYTE* target = reinterpret_cast<BYTE*>(reinterpret_cast<uintptr_t>(game) + 0x16d940);
    const BYTE signature[] = {0x55,0x8B,0xEC,0x83,0xE4,0xF8,0x8B,0x45,0x08,0x83,0xEC,0x0C};
    if (memcmp(target, signature, sizeof(signature)) != 0) { Log("init signature mismatch at %p", target); return false; }
    g_trampoline = reinterpret_cast<BYTE*>(VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!g_trampoline) return false;
    memcpy(g_trampoline, target, 6); g_trampoline[6] = 0xE9;
    *reinterpret_cast<int32_t*>(g_trampoline + 7) = static_cast<int32_t>((target + 6) - (g_trampoline + 11));
    DWORD oldProtect = 0; if (!VirtualProtect(target, 6, PAGE_EXECUTE_READWRITE, &oldProtect)) return false;
    target[0] = 0xE9; *reinterpret_cast<int32_t*>(target + 1) = static_cast<int32_t>(reinterpret_cast<BYTE*>(&HookInit) - (target + 5)); target[5] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), target, 6); DWORD ignored = 0; VirtualProtect(target, 6, oldProtect, &ignored);
    BYTE* layout = reinterpret_cast<BYTE*>(reinterpret_cast<uintptr_t>(game) + 0x16e400);
    const BYTE layoutSig[] = {0x8B,0x44,0x24,0x04,0x0F,0x57,0xE4};
    if (memcmp(layout, layoutSig, sizeof(layoutSig)) != 0) { Log("layout signature mismatch at %p", layout); return true; }
    g_layoutTrampoline = reinterpret_cast<BYTE*>(VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!g_layoutTrampoline) return true;
    memcpy(g_layoutTrampoline, layout, 7); g_layoutTrampoline[7] = 0xE9;
    *reinterpret_cast<int32_t*>(g_layoutTrampoline + 8) = static_cast<int32_t>((layout + 7) - (g_layoutTrampoline + 12));
    if (!VirtualProtect(layout, 7, PAGE_EXECUTE_READWRITE, &oldProtect)) return true;
    layout[0] = 0xE9; *reinterpret_cast<int32_t*>(layout + 1) = static_cast<int32_t>(reinterpret_cast<BYTE*>(&HookLayout) - (layout + 5)); layout[5] = 0x90; layout[6] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), layout, 7); VirtualProtect(layout, 7, oldProtect, &ignored);
    Log("patched init at %p and layout at %p", target, layout); return true;
}
static DWORD WINAPI PatchThread(void*) {
    ReadConfig();
    for (int i = 0; i < 200; ++i) {
        if (GetModuleHandleA("game.exe")) {
            return PatchInit() ? 0 : 0;
        }
        Sleep(50);
    }
    Log("game.exe module not found"); return 0;
}
static void LoadRealD3D9() {
    if (g_realD3D9) return;
    char sys[MAX_PATH] = {}; GetSystemDirectoryA(sys, MAX_PATH); strcat_s(sys, "\\d3d9.dll");
    g_realD3D9 = LoadLibraryA(sys);
    if (!g_realD3D9) { Log("LoadLibrary real d3d9 failed"); return; }
    g_realCreate9 = reinterpret_cast<Direct3DCreate9Fn>(GetProcAddress(g_realD3D9, "Direct3DCreate9"));
    Log("real d3d9=%p Direct3DCreate9=%p", g_realD3D9, g_realCreate9);
}
__declspec(dllexport) void* WINAPI Direct3DCreate9(UINT sdkVersion) {
    LoadRealD3D9();
    void* obj = g_realCreate9 ? g_realCreate9(sdkVersion) : nullptr;
    if (obj) PatchD3D9Vtable(obj);
    return obj;
}
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h); InitializeCriticalSection(&g_logLock); g_logReady = true; Log("loaded d3d9 proxy");
        CreateThread(nullptr, 0, PatchThread, nullptr, 0, nullptr);
    } else if (reason == DLL_PROCESS_DETACH) { g_logReady = false; DeleteCriticalSection(&g_logLock); if (g_realD3D9) FreeLibrary(g_realD3D9); }
    return TRUE;
}

