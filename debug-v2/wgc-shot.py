"""Game-owned Windows Graphics Capture, using the native binding directly (Pillow encoding)."""
import importlib,pathlib,sys,types,threading,runpy
import numpy as np
from PIL import Image
from harness import ROOT
state=runpy.run_path(str(ROOT/'debug-v2/window-shot.py'))
# Avoid the optional OpenCV image writer in the package wrapper; use the native API.
package=types.ModuleType('windows_capture');package.__path__=[str(ROOT/'tools-v2/pydeps/windows_capture')];sys.modules['windows_capture']=package
binding=importlib.import_module('windows_capture.windows_capture')
done=threading.Event();errors=[]
def frame(native,length,width,height,stop,timestamp):
    try:
        a=np.frombuffer(native.buffer_view(),dtype=np.uint8,count=length).reshape(height,native.bytes_per_row)[:,:width*4].reshape(height,width,4)
        Image.fromarray(a[:,:,[2,1,0]].copy()).save(ROOT/'diagnostics-v2/wgc-window.png')
    except Exception as e:errors.append(str(e))
    finally:stop[0]=True;done.set()
capture=binding.NativeWindowsCapture(frame,done.set,False,False,False,None,False,None,None,state['hwnd'])
control=capture.start_free_threaded()
try:
    if not done.wait(8):raise RuntimeError('No WGC frame received')
finally:control.stop()
if errors:raise RuntimeError(errors)
print({'captured':'wgc-window.png','hwnd':state['hwnd']})
