"""Capture only the verified game HWND using PrintWindow. No desktop input."""
import ctypes,pathlib
from ctypes import wintypes as W
from PIL import Image
from harness import identify,ROOT
pid=identify();u=ctypes.WinDLL('user32',use_last_error=True);g=ctypes.WinDLL('gdi32',use_last_error=True)
CB=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM);windows=[]
u.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)];u.GetWindowThreadProcessId.restype=W.DWORD
u.IsWindowVisible.argtypes=[W.HWND];u.IsWindowVisible.restype=W.BOOL
u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int];u.GetClassNameW.restype=ctypes.c_int
@CB
def visit(hwnd,_):
    owner=W.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
    if owner.value==pid:
        name=ctypes.create_unicode_buffer(256);u.GetClassNameW(hwnd,name,256)
        if name.value=='CASTLEVANIAADVANCECOLLECTION':windows.append(hwnd)
    return True
u.EnumWindows.argtypes=[CB,W.LPARAM];u.EnumWindows(visit,0)
if len(windows)!=1:raise RuntimeError(f'Ambiguous visible game windows: {windows}')
hwnd=windows[0];r=W.RECT();u.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)];u.GetWindowRect(hwnd,ctypes.byref(r));w,h=r.right-r.left,r.bottom-r.top
u.GetDC.argtypes=[W.HWND];u.GetDC.restype=W.HDC;u.ReleaseDC.argtypes=[W.HWND,W.HDC]
g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
g.CreateCompatibleBitmap.argtypes=[W.HDC,ctypes.c_int,ctypes.c_int];g.CreateCompatibleBitmap.restype=W.HBITMAP
g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ];g.SelectObject.restype=W.HGDIOBJ
g.DeleteObject.argtypes=[W.HGDIOBJ];g.DeleteDC.argtypes=[W.HDC]
u.PrintWindow.argtypes=[W.HWND,W.HDC,W.UINT];u.PrintWindow.restype=W.BOOL
class Header(ctypes.Structure):_fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bpp',W.WORD),('compression',W.DWORD),('imageSize',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
g.GetDIBits.argtypes=[W.HDC,W.HBITMAP,W.UINT,W.UINT,W.LPVOID,ctypes.POINTER(Header),W.UINT];g.GetDIBits.restype=ctypes.c_int
dc=u.GetDC(hwnd);mem=g.CreateCompatibleDC(dc);bitmap=g.CreateCompatibleBitmap(dc,w,h);old=g.SelectObject(mem,bitmap)
try:
    if not u.PrintWindow(hwnd,mem,2):raise ctypes.WinError(ctypes.get_last_error())
    header=Header(ctypes.sizeof(Header),w,-h,1,32,0,w*h*4,0,0,0,0);data=ctypes.create_string_buffer(w*h*4)
    if g.GetDIBits(mem,bitmap,0,h,data,ctypes.byref(header),0)!=h:raise RuntimeError('Incomplete bitmap capture')
    Image.frombytes('RGB',(w,h),data.raw,'raw','BGRX').save(ROOT/'diagnostics-v2/window.png');print({'pid':pid,'hwnd':hwnd,'width':w,'height':h})
finally:g.SelectObject(mem,old);g.DeleteObject(bitmap);g.DeleteDC(mem);u.ReleaseDC(hwnd,dc)
