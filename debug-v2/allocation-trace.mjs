import {gameExe} from './debug-paths.mjs';
// Read-only allocation observer. No input or allocation-return changes.
import * as frida from 'frida';
import fs from 'node:fs';
import crypto from 'node:crypto';
const exe=gameExe;
if(crypto.createHash('sha256').update(fs.readFileSync(exe)).digest('hex')!=='404e78ade8b92fe3a89aa2ed3e7de8bde3545d694e669835a81145f5e026e6bb')throw Error('Unsupported EXE');
const pid=Number(process.argv[2]),log=process.argv[3],seconds=Number(process.argv[4]??90);
if(!Number.isInteger(pid)||pid<1||!log||seconds<10||seconds>300)throw Error('Expected verified PID, log, bounded seconds');
const session=await frida.attach(pid);
const script=await session.createScript(`
const game=Process.getModuleByName('game.exe');if(game.path.toLowerCase()!==${JSON.stringify(exe.toLowerCase())})throw Error('Unexpected process');
const ntdll=Process.getModuleByName('ntdll.dll');
function frame(address){const module=Process.findModuleByAddress(address);return module?module.name+'+'+address.sub(module.base):address.toString();}
for(const name of ['NtAllocateVirtualMemory','NtAllocateVirtualMemoryEx']){
 const target=ntdll.findExportByName(name);if(!target)continue;
 Interceptor.attach(target,{
  onEnter(args){
   this.observe=false;
   if(args[0].toUInt32()!==0xffffffff)return;
   const requested=args[3].readU32();if(requested<1024*1024)return;
   this.observe=true;this.basePointer=args[1];this.sizePointer=args[3];
   this.record={time:Date.now(),type:name,requested,allocationType:args[4].toUInt32(),
     accurate:Thread.backtrace(this.context,Backtracer.ACCURATE).map(frame),
     fuzzy:Thread.backtrace(this.context,Backtracer.FUZZY).map(frame)};
  },
  onLeave(ret){if(this.observe)send({...this.record,result:ret.toInt32(),address:this.basePointer.readPointer().toString(),allocated:this.sizePointer.readU32()});}
 });
}
`);
script.message.connect(message=>fs.appendFileSync(log,JSON.stringify(message.type==='send'?message.payload:message)+'\n'));
try{await script.load();console.log(JSON.stringify({ready:true,pid,seconds}));await new Promise(resolve=>{const timer=setTimeout(resolve,seconds*1000);session.detached.connect(()=>{clearTimeout(timer);resolve();});});}
finally{if(!session.isDetached){await script.unload();await session.detach();}}
