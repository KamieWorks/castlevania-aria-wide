"""Bounded window-message input to the verified game HWND, never global input."""
import ctypes,time,runpy,argparse
from harness import ROOT
from ctypes import wintypes as W
p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('--ms',type=int,default=200);a=p.parse_args()
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'));hwnd=state['hwnd']
keys={'z':(90,0x2c),'x':(88,0x2d),'enter':(13,0x1c),'up':(38,0x48),'down':(40,0x50),'left':(37,0x4b),'right':(39,0x4d)};vk,scan=keys[a.key]
u=ctypes.WinDLL('user32',use_last_error=True);u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];u.PostMessageW.restype=W.BOOL
extended=(1<<24) if a.key in ['up','down','left','right'] else 0
if not u.PostMessageW(hwnd,0x100,vk,1|(scan<<16)|extended):raise ctypes.WinError(ctypes.get_last_error())
try:time.sleep(min(max(a.ms,50),3000)/1000)
finally:u.PostMessageW(hwnd,0x101,vk,1|(scan<<16)|extended|(3<<30))
print({'key':a.key,'released':True})
