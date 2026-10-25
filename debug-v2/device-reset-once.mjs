import {gameExe} from './debug-paths.mjs';
// Diagnostic-only: report one failed Present to exercise the game's own Reset
// path. Does not change display mode or invoke Reset from a foreign thread.
import * as frida from 'frida';
const pid=Number(process.argv[2]);if(!Number.isInteger(pid)||pid<1)throw Error('Expected verified PID');
const session=await frida.attach(pid);
let finish;const done=new Promise(resolve=>finish=resolve);
const script=await session.createScript(`
const game=Process.getModuleByName('game.exe');
if(game.path.toLowerCase()!==${JSON.stringify(gameExe.toLowerCase())})throw Error('Unexpected process path');
let device=null,injected=false,resetReturned=false,afterFrames=0,presentCalls=0,matchingCalls=0;
const hooks=[],events=[];
function event(value){events.push({time:Date.now(),...value});}
hooks.push(Interceptor.attach(game.base.add(0x16de60),{onEnter(){
 const renderer=this.context.ecx,actual=renderer.add(8).readPointer();
 if(device){if(resetReturned&&++afterFrames>=60)send({done:true,events});return;}
 const pp=renderer.add(12),windowed=pp.add(32).readU32();
 if(actual.isNull()||windowed!==1)throw Error('Only the existing windowed device is eligible');
 device=actual;const table=device.readPointer();event({type:'attached',device:device.toString(),windowed,present:table.add(17*4).readPointer().toString()});
 hooks.push(Interceptor.attach(table.add(17*4).readPointer(),{
  onEnter(args){this.target=args[0].equals(device);presentCalls++;if(this.target)matchingCalls++;if(presentCalls<=3)event({type:'Present-enter',arg0:args[0].toString(),ecx:this.context.ecx.toString(),matches:this.target});},
  onLeave(ret){if(presentCalls<=3)event({type:'Present-return',result:ret.toInt32(),matches:this.target});if(this.target&&!injected&&ret.toInt32()>=0){injected=true;event({type:'synthetic-Present-device-lost',original:ret.toInt32()});ret.replace(ptr(0x88760868));}}
 }));
 hooks.push(Interceptor.attach(table.add(16*4).readPointer(),{
  onEnter(args){this.target=args[0].equals(device);if(this.target)event({type:'native-Reset-enter',width:args[1].readU32(),height:args[1].add(4).readU32(),windowed:args[1].add(32).readU32()});},
  onLeave(ret){if(this.target){event({type:'native-Reset-return',result:ret.toInt32()});resetReturned=ret.toInt32()===0;}}
 }));
}}));
rpc.exports.result=()=>({injected,resetReturned,afterFrames,presentCalls,matchingCalls,events});
`);
script.message.connect(message=>{if(message.type==='send'&&message.payload.done)finish(message.payload);else if(message.type==='error')finish({error:message.description});});
try{
 await script.load();
 const result=await Promise.race([done,new Promise(resolve=>setTimeout(()=>resolve({timeout:true}),15000))]);
 console.log(JSON.stringify({...result,...await script.exports.result()}));
}finally{await script.unload();await session.detach();}
