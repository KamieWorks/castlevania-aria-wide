// Read-only allocation/lifetime tracing around the reproducible shutdown fault.
import * as frida from 'frida';
const session=await frida.attach(Number(process.argv[2]));
const path=JSON.stringify(process.argv[3]);
const fix=process.argv.includes('--fix-movie-child'),fixState=process.argv.includes('--fix-state-head');
const script=await session.createScript(`
const base=Process.getModuleByName('game.exe').base;
const f=new File(${path},'w'),allocations=new Map(),tasks=new Set();let sequence=0;
function log(r){f.write(JSON.stringify(r)+'\\n');f.flush();}
function address(p){return p.toString();}
function stack(context){return Thread.backtrace(context,Backtracer.ACCURATE).map(p=>{const m=Process.findModuleByAddress(p);return m?m.name+'+'+p.sub(m.base):p.toString();});}
const hooks=[];
hooks.push(Interceptor.attach(base.add(0x153e80),{
 onEnter(){if(!this.returnAddress.equals(base.add(0x38642)))return;const list=this.context.ecx;let node=list.add(0x10).readPointer();const tasks=[];for(let n=0;!node.isNull()&&n<12;n++,node=node.add(4).readPointer())tasks.push(address(node.readPointer()));log({type:'movie-list',child:address(list.add(0x1c).readPointer()),tasks});},
 onLeave(){const m=Process.getModuleByName('d3d9.dll'),fn=m.findExportByName('GetShutdownCounters');if(fn){const out=Memory.alloc(12);new NativeFunction(fn,'void',['pointer'],'mscdecl')(out);log({type:'native-shutdown-counters',counters:[0,4,8].map(o=>out.add(o).readU32())});}}
}));
if(${fixState}){
 const destroying=new Map(),freeState=new NativeFunction(base.add(0x38c20),'void',['pointer'],'thiscall');
 const clearState=new NativeFunction(base.add(0x38c80),'void',['pointer'],'thiscall');
 const free=new NativeFunction(base.add(0x1ec696),'void',['pointer'],'mscdecl');
 hooks.push(Interceptor.attach(base.add(0xe570),{
  onEnter(){this.thread=Process.getCurrentThreadId();this.prior=destroying.get(this.thread);this.job={parent:this.context.ecx,heads:[0x168,0x16c].map(o=>this.context.ecx.add(o).readPointer()),deferred:[]};destroying.set(this.thread,this.job);log({type:'emu-destroy',parent:address(this.job.parent),heads:this.job.heads.map(address)});},
  onLeave(){for(const head of this.job.deferred){free(head);log({type:'release-deferred-state-head',head:address(head),time:Date.now()});}if(this.prior)destroying.set(this.thread,this.prior);else destroying.delete(this.thread);}
 }));
 const replacement=new NativeCallback(function(head){
  const job=destroying.get(Process.getCurrentThreadId());
  log({type:'state-free',head:address(head),caller:this.returnAddress.sub(base).toString(),firstNode:address(head.readPointer())});
  if(job&&job.heads.some(p=>p.equals(head))&&[0xe5f7,0xe606].some(o=>this.returnAddress.equals(base.add(o)))){clearState(head);job.deferred.push(head);log({type:'defer-state-head',head:address(head),time:Date.now()});}
  else freeState(head);
 },'void',['pointer'],'thiscall');
 Interceptor.replace(base.add(0x38c20),replacement);
}
hooks.push(Interceptor.attach(base.add(0x1ec6b1),{
 onEnter(args){this.size=args[0].toUInt32();},
 onLeave(ret){if(!ret.isNull())allocations.set(address(ret),{generation:++sequence,size:this.size,freed:false});}
}));
hooks.push(Interceptor.attach(base.add(0x1ec696),{
 onEnter(args){const p=address(args[0]);if(args[0].isNull())return;const previous=allocations.get(p);
  if(tasks.has(p)||previous?.freed)log({type:'free',pointer:p,previous,caller:this.returnAddress.sub(base).toString(),stack:stack(this.context),time:Date.now()});
  const caller=this.returnAddress.sub(base).toUInt32();
  allocations.set(p,{...previous,freed:true,freeCaller:'0x'+caller.toString(16),firstFreeStack:[0x1dbef7,0x38c41].includes(caller)?stack(this.context):null});
 }
}));
hooks.push(Interceptor.attach(base.add(0x5920),{
 onEnter(){const p=address(this.context.ecx);tasks.add(p);let bytes=null;
  try{bytes=Array.from(new Uint8Array(this.context.ecx.sub(8).readByteArray(32)));}catch(e){}
  log({type:'task-delete',pointer:p,allocation:allocations.get(p),caller:this.returnAddress.sub(base).toString(),bytes,time:Date.now()});
 }
}));
log({type:'armed',base:base.toString(),time:Date.now()});
if(${fix})hooks.push(Interceptor.attach(base.add(0x38642),{
 onEnter(){
   const parent=this.context.edi,field=parent.add(0x48),child=field.readPointer();
   if(child.isNull())return;const previous=allocations.get(address(child));
   let vtable=null;try{vtable=child.readPointer();}catch(e){}
   log({type:'movie-child',parent:address(parent),child:address(child),previous,vtable:vtable?address(vtable):null,time:Date.now()});
   if(previous?.freed&&vtable?.equals(base.add(0x22668c))){field.writePointer(ptr(0));log({type:'skip-already-deleted-movie-child',child:address(child),time:Date.now()});}
 }
}));
setTimeout(()=>{for(const h of hooks)h.detach();log({type:'bounded-stop',time:Date.now()});f.close();},10000);
`);
script.message.connect(m=>{if(m.type==='error')process.stderr.write(JSON.stringify(m)+'\n');});
await script.load();process.stdout.write('{"ready":true}\n');
let timer;await Promise.race([new Promise(resolve=>session.detached.connect(resolve)),new Promise(resolve=>{timer=setTimeout(resolve,11000);})]);
if(timer)clearTimeout(timer);
try{await script.unload();await session.detach();}catch(e){}
