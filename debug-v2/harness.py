"""Exact-build, process-local Aria diagnostics. No global keyboard or mouse input.

Examples: python debug-v2/harness.py capture baseline --full
          python debug-v2/harness.py sequence title z:350 wait:1000 enter:350 capture:after
"""
from debug_config import debug_root, game_exe
import argparse, ctypes, hashlib, json, os, pathlib, subprocess, sys, time
from ctypes import wintypes as W
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXE=game_exe()
EXPECTED='404e78ade8b92fe3a89aa2ed3e7de8bde3545d694e669835a81145f5e026e6bb'
KEYS={'z':0x2c,'x':0x2d,'a':0x1e,'s':0x1f,'enter':0x1c,'tab':0x0f,'f1':0x3b,'up':0xc8,'down':0xd0,'left':0xcb,'right':0xcd,'escape':1}

def identify():
    if hashlib.sha256(EXE.read_bytes()).hexdigest()!=EXPECTED: raise RuntimeError('Unsupported executable hash')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    ps=ctypes.WinDLL('psapi',use_last_error=True)
    ps.EnumProcesses.argtypes=[ctypes.POINTER(W.DWORD),W.DWORD,ctypes.POINTER(W.DWORD)];ps.EnumProcesses.restype=W.BOOL
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)];k.QueryFullProcessImageNameW.restype=W.BOOL
    k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
    ids=(W.DWORD*8192)();used=W.DWORD()
    if not ps.EnumProcesses(ids,ctypes.sizeof(ids),ctypes.byref(used)):raise ctypes.WinError(ctypes.get_last_error())
    found=[]
    for pid in ids[:used.value//4]:
        h=k.OpenProcess(0x1000,False,pid)
        if not h:continue
        try:
            path=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(path))
            if k.QueryFullProcessImageNameW(h,0,path,ctypes.byref(size)) and os.path.normcase(path.value)==os.path.normcase(str(EXE)):found.append(pid)
        finally:k.CloseHandle(h)
    if len(found)!=1:raise RuntimeError(f'Expected one verified game process, found {found}')
    return found[0]

class Probe:
    def __enter__(self):
        self.pid=identify();self.counter=0
        self.proc=subprocess.Popen(['node',str(ROOT/'debug-v2/bridge.mjs'),str(self.pid)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        if not json.loads(self.proc.stdout.readline()).get('ready'):raise RuntimeError('Bridge handshake failed')
        time.sleep(.3)
        return self
    def call(self,method,*args):
        self.counter+=1;self.proc.stdin.write(json.dumps({'id':self.counter,'method':method,'args':args})+'\n');self.proc.stdin.flush()
        line=self.proc.stdout.readline()
        if not line:raise RuntimeError('Bridge exited')
        response=json.loads(line)
        if 'error' in response:raise RuntimeError(response['error'])
        return response['result']
    def capture(self,name,full=False,at_present=False,scan_reference=False):
        if not name.replace('-','').replace('_','').isalnum():raise ValueError('Use a simple capture label')
        tmp=debug_root();tmp.mkdir(exist_ok=True)
        prefix=tmp/name
        meta=self.call('capturescanpresent' if scan_reference else 'capturepresent' if at_present else 'capture',str(prefix).replace('\\','/'),full)
        out=ROOT/'diagnostics-v2'/name;out.parent.mkdir(exist_ok=True)
        pixels=np.frombuffer(prefix.with_suffix('.rgb555').read_bytes(),dtype='<u2').reshape(meta['height'],meta['width'])
        rgb=np.stack([(pixels>>n)&31 for n in (0,5,10)],axis=-1).astype(np.uint8);rgb=(rgb<<3)|(rgb>>2)
        Image.fromarray(rgb).resize((meta['width']*4,meta['height']*4),Image.Resampling.NEAREST).save(out.with_suffix('.png'))
        meta.update(pid=self.pid,sha256=EXPECTED,frame_sha256=hashlib.sha256(pixels.tobytes()).hexdigest())
        out.with_suffix('.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        if full:
            private=ROOT/'private-v2/captures';private.mkdir(exist_ok=True)
            for ext in ['ppu','ewram','iwram','rgb555']:(private/(name+'.'+ext)).write_bytes(prefix.with_suffix('.'+ext).read_bytes())
            if scan_reference:(private/(name+'.scan.ppu')).write_bytes((tmp/(name+'.scan.ppu')).read_bytes())
        print(json.dumps({'capture':str(out.with_suffix('.png')),'frame':meta['frame_sha256']},ensure_ascii=False))
        return meta
    def __exit__(self,*exc):
        self.proc.stdin.close()
        try:self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait();raise RuntimeError('Bridge detach timed out')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['capture','sequence']);p.add_argument('label');p.add_argument('steps',nargs='*');p.add_argument('--full',action='store_true');args=p.parse_args()
    with Probe() as probe:
        probe.capture(args.label,args.full)
        for step in args.steps:
            key,value=step.split(':',1)
            if key=='wait':time.sleep(min(int(value),10000)/1000)
            elif key=='capture':probe.capture(value,args.full)
            else:print(json.dumps({'key':key,**probe.call('pulse',[KEYS[k] for k in key.split('+')],int(value))}))
if __name__=='__main__':main()
