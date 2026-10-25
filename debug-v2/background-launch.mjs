import {debugRoot} from './debug-paths.mjs';
// Diagnostic-only launcher: prevent this game process from activating windows.
import * as frida from 'frida';
const device=await frida.getLocalDevice();
const inputGuardPath=debugRoot.replaceAll('\\','/')+'/debug-input-v1.dll';
const pid=await device.spawn(process.argv[2],{cwd:process.argv[3],stdio:'pipe',env:{SteamAppId:'1552550',SteamGameId:'1552550'}});
const session=await device.attach(pid);
const script=await session.createScript(`
let configured=false;const callbacks=[];
const game=Process.getModuleByName('game.exe').base;
const kernel=Process.getModuleByName('kernel32.dll');
const inputGuard=Module.load(${JSON.stringify(inputGuardPath)});
const inputInstalled=new NativeFunction(inputGuard.getExportByName('InstallDebugInput'),'int',[],'mscdecl')();
if(inputInstalled!==0)throw Error('Native diagnostic input setup failed: '+inputInstalled);
const createEvent=new NativeFunction(kernel.getExportByName('CreateEventW'),'pointer',['pointer','int','int','pointer'],'stdcall');
const waitEvent=new NativeFunction(kernel.getExportByName('WaitForSingleObject'),'uint',['pointer','uint'],'stdcall');
const inputEvent=createEvent(ptr(0),1,0,Memory.allocUtf16String('Local\\\\AriaWideDebugInput-'+Process.id));
if(inputEvent.isNull())throw Error('Cannot create background input guard');
let keyboardHook=null,keyboardDevice=null;
const releasedKeyboard=new Uint8Array(256);
setInterval(()=>{
 try{
  const device=game.add(0x2844d4).readPointer();if(device.isNull()||(keyboardDevice&&keyboardDevice.equals(device)))return;
  if(keyboardHook){keyboardHook.detach();Interceptor.flush();}keyboardDevice=device;
  keyboardHook=Interceptor.attach(device.readPointer().add(36).readPointer(),{
   onEnter(args){this.keyboard=args[0].equals(device)&&args[1].toUInt32()===256;this.buffer=args[2];},
   onLeave(ret){if(this.keyboard&&waitEvent(inputEvent,0)!==0){this.buffer.writeByteArray(releasedKeyboard);ret.replace(0);}}
  });
 }catch(e){}
},25);
// GBA isolation/pulses use the diagnostic DLL's register-preserving detour.
// Do not attach GumJS/CModule adapters at instruction addresses inside it.
const observer=Process.attachModuleObserver({onAdded(module){
 if(configured||module.name.toLowerCase()!=='user32.dll')return;configured=true;
 for(const name of ['SetForegroundWindow','BringWindowToTop','SetActiveWindow','SetFocus']){
  const fn=module.findExportByName(name);if(!fn)continue;
  const pointerReturn=['SetActiveWindow','SetFocus'].includes(name);
  const callback=new NativeCallback(function(){return pointerReturn?ptr(0):1;},pointerReturn?'pointer':'int',['pointer'],'stdcall');
  callbacks.push(callback);Interceptor.replace(fn,callback);
 }
 const switchWindow=module.findExportByName('SwitchToThisWindow');
 if(switchWindow){const callback=new NativeCallback(function(){},'void',['pointer','int'],'stdcall');callbacks.push(callback);Interceptor.replace(switchWindow,callback);}
 for(const name of ['ShowWindow','ShowWindowAsync']){
  const fn=module.findExportByName(name);if(fn)Interceptor.attach(fn,{onEnter(args){args[1]=ptr(0);}});
 }
 const position=module.findExportByName('SetWindowPos');
 if(position)Interceptor.attach(position,{onEnter(args){args[6]=ptr((args[6].toUInt32()|0x90)&~0x40);}});
 const placement=module.findExportByName('SetWindowPlacement');
 if(placement)Interceptor.attach(placement,{onEnter(args){this.copy=Memory.alloc(44);Memory.copy(this.copy,args[1],44);this.copy.add(8).writeU32(0);args[1]=this.copy;}});
 for(const name of ['CreateWindowExW','CreateWindowExA']){
  const fn=module.findExportByName(name);if(fn)Interceptor.attach(fn,{onEnter(args){args[0]=ptr(args[0].toUInt32()|0x08000000);args[3]=ptr(args[3].toUInt32()&~0x10000000);}});
 }
}});
`);
script.message.connect(m=>{if(m.type==='error')process.stderr.write(JSON.stringify(m)+'\n');});
try{await script.load();await device.resume(pid);}
catch(error){await device.kill(pid);await session.detach();throw error;}
process.stdout.write(JSON.stringify({pid,backgroundGuard:true})+'\n');
const keepAlive=setInterval(()=>{},1000);
await new Promise(resolve=>session.detached.connect(resolve));
clearInterval(keepAlive);
