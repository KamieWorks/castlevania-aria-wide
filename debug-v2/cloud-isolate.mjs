// Diagnostic-only: divert this game's synchronous cloud writes to local private
// files. Unsupported async/stream writes fail locally rather than reaching Steam.
import * as frida from 'frida';
import fs from 'node:fs';
const pid=Number(process.argv[2]),directory=process.argv[3];
fs.mkdirSync(directory,{recursive:true});const log=directory+'/events.jsonl';
const session=await frida.attach(pid);
const script=await session.createScript(`
const api=Process.getModuleByName('steam_api.dll');
const user=new NativeFunction(api.getExportByName('SteamAPI_GetHSteamUser'),'int',[],'mscdecl')();
const storage=new NativeFunction(api.getExportByName('SteamInternal_FindOrCreateUserInterface'),'pointer',['int','pointer'],'mscdecl')(user,Memory.allocUtf8String('STEAMREMOTESTORAGE_INTERFACE_VERSION014'));
if(storage.isNull())throw Error('Game remote storage is unavailable');
const table=storage.readPointer(),callbacks=[];let sequence=0;
const specifications=[
 {slot:0,name:'FileWrite',ret:'int',args:['pointer','pointer','pointer','int']},
 {slot:2,name:'FileWriteAsync',ret:'uint64',args:['pointer','pointer','pointer','int']},
 {slot:5,name:'FileForget',ret:'int',args:['pointer','pointer']},
 {slot:6,name:'FileDelete',ret:'int',args:['pointer','pointer']},
 {slot:7,name:'FileShare',ret:'uint64',args:['pointer','pointer']},
 {slot:8,name:'SetSyncPlatforms',ret:'int',args:['pointer','pointer','int']},
 {slot:9,name:'FileWriteStreamOpen',ret:'uint64',args:['pointer','pointer']},
 {slot:10,name:'FileWriteStreamWriteChunk',ret:'int',args:['pointer','uint64','pointer','int']},
 {slot:11,name:'FileWriteStreamClose',ret:'int',args:['pointer','uint64']},
 {slot:12,name:'FileWriteStreamCancel',ret:'int',args:['pointer','uint64']}
];
const targets=specifications.map(s=>table.add(s.slot*Process.pointerSize).readPointer());
if(new Set(targets.map(p=>p.toString())).size!==targets.length)throw Error('Aliased storage implementations; refusing ambiguous hooks');
for(let index=0;index<specifications.length;index++){
 const spec=specifications[index],target=targets[index];
 const callback=new NativeCallback(function(...args){
  // SDK calls may use another cached interface instance. This instrumentation
  // is process-local; protect every call to this implementation in the game.
  const event={type:spec.name,sequence:++sequence,time:Date.now(),forwarded:false};
  if([0,2,5,6,7,8,9].includes(spec.slot))event.name=args[1].readCString();
  if([0,2,10].includes(spec.slot)){
   const count=args[3];event.bytes=count;
   if(count>=0&&count<=32*1024*1024){const path=${JSON.stringify(directory)}+'/write-'+event.sequence+'.bin';const file=new File(path,'wb');try{if(count)file.write(args[2].readByteArray(count));}finally{file.close();}event.localPath=path;}
   else event.error='Unexpected write size; blocked';
  }
  const owner=Process.findModuleByAddress(this.returnAddress);event.caller=owner?owner.name+'+'+this.returnAddress.sub(owner.base):this.returnAddress.toString();
  send(event);
  if(spec.slot===2||spec.slot===7)return new UInt64(0);
  if(spec.slot===9)return new UInt64('0xffffffffffffffff');
  return spec.slot===10?0:1;
 },spec.ret,spec.args,'thiscall');
 callbacks.push(callback);Interceptor.replace(target,callback);
}
const stats=new NativeFunction(api.getExportByName('SteamInternal_FindOrCreateUserInterface'),'pointer',['int','pointer'],'mscdecl')(user,Memory.allocUtf8String('STEAMUSERSTATS_INTERFACE_VERSION012'));
if(stats.isNull())throw Error('Cannot protect achievement/statistics interface');
const statsTable=stats.readPointer();
const statMethods=[
 {slot:3,name:'SetStatFloat',args:['pointer','pointer','float']},
 {slot:4,name:'SetStatInt32',args:['pointer','pointer','int']},
 {slot:5,name:'UpdateAvgRateStat',args:['pointer','pointer','float','double']},
 {slot:7,name:'SetAchievement',args:['pointer','pointer']},
 {slot:8,name:'ClearAchievement',args:['pointer','pointer']},
 {slot:10,name:'StoreStats',args:['pointer']},
 {slot:21,name:'ResetAllStats',args:['pointer','int']},
 {slot:31,name:'UploadLeaderboardScore',args:['pointer','uint64','int','int','pointer','int'],ret:'uint64'}
];
for(const spec of statMethods){
 const callback=new NativeCallback(function(...args){
  const event={type:spec.name,time:Date.now(),forwarded:false};
  if([3,4,5,7,8].includes(spec.slot))event.name=args[1].readCString();
  send(event);return spec.ret==='uint64'?new UInt64(0):0;
 },spec.ret??'int',spec.args,'thiscall');
 callbacks.push(callback);Interceptor.replace(statsTable.add(spec.slot*4).readPointer(),callback);
}
const getCount=new NativeFunction(api.getExportByName('SteamAPI_ISteamUserStats_GetNumAchievements'),'uint',['pointer'],'mscdecl');
const getName=new NativeFunction(api.getExportByName('SteamAPI_ISteamUserStats_GetAchievementName'),'pointer',['pointer','uint'],'mscdecl');
const getAchievement=new NativeFunction(api.getExportByName('SteamAPI_ISteamUserStats_GetAchievement'),'int',['pointer','pointer','pointer'],'mscdecl');
function achievementState(){const count=getCount(stats),result=[];if(count>512)throw Error('Unexpected achievement count');for(let i=0;i<count;i++){const name=getName(stats,i),out=Memory.alloc(1);out.writeU8(0);const valid=!!(getAchievement(stats,name,out)&255);result.push({name:name.readCString(),valid,unlocked:valid?!!out.readU8():null});}return result;}
const initialAchievements=achievementState();send({type:'achievement-baseline',count:initialAchievements.length});
Interceptor.attach(api.getExportByName('SteamAPI_Shutdown'),{onEnter(){const current=achievementState();const comparable=current.filter((r,i)=>r.valid&&initialAchievements[i]?.valid);send({type:'achievement-comparison',count:current.length,comparable:comparable.length,changed:comparable.filter(r=>r.unlocked!==initialAchievements.find(x=>x.name===r.name)?.unlocked).length});}});
rpc.exports.stats=()=>({isolated:true,storage:storage.toString(),hooks:specifications.length+statMethods.length,achievementsProtected:true});
`);
script.message.connect(message=>{
 if(message.type==='send')fs.appendFileSync(log,JSON.stringify(message.payload)+'\n');
 else if(message.type==='error'){fs.appendFileSync(log,JSON.stringify({error:message.description,stack:message.stack})+'\n');process.stderr.write(JSON.stringify(message)+'\n');}
});
await script.load();const status=await script.exports.stats();process.stdout.write(JSON.stringify({ready:true,pid,...status})+'\n');
const keepAlive=setInterval(()=>{},1000);
await new Promise(resolve=>session.detached.connect((reason,crash)=>{fs.appendFileSync(log,JSON.stringify({type:'detached',reason,crash:crash?.summary??null})+'\n');resolve();}));
clearInterval(keepAlive);
