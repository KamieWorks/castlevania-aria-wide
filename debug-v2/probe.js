'use strict';
const base = Process.getModuleByName('game.exe').base;
const inputGuard=Process.getModuleByName('debug-input-v1.dll');
const nativePadPulse=new NativeFunction(inputGuard.getExportByName('SetPadPulse'),'int',['uint','uint'],'mscdecl');
const nativePadCounters=new NativeFunction(inputGuard.getExportByName('GetPadCounters'),'void',['pointer'],'mscdecl');
const inputCountBuffer=Memory.alloc(12);
function padCounts(){nativePadCounters(inputCountBuffer);if(inputCountBuffer.add(8).readU32()!==1)throw Error('Native diagnostic input is not installed');return {input:inputCalls+inputCountBuffer.readU32(),forced:forcedCalls+inputCountBuffer.add(4).readU32()};}
function armPad(mask,ms){if(nativePadPulse(mask,ms)!==0)throw Error('Native bounded pulse rejected');}
let context = null;
let pending = [];
let pendingPresent=[];
let presentCaptureHook=null;
let scanReferenceHook=null,scanReferences=[];
let denseJob=null,denseScanHook=null;
let cloudPrevious=null;
function cloudActors(){
  if(!context)return null;const ram=context.add(0x150),actors=[];
  for(let i=0;i<224;i++){
    const e=ram.add(0x4e4+i*0x84);
    if(e.add(0x5c).readU8()!==30||e.readU32()<0x08000001||e.readU32()>0x08800000)continue;
    actors.push({i,fn:e.readU32(),draw:e.add(4).readU32(),stage:e.add(10).readU8(),palette:(e.add(0x5a).readU8()>>3)&15,x:e.add(0x40).readS32(),y:e.add(0x44).readS32(),vx:e.add(0x48).readS32(),frame:e.add(0x64).readU8()});
  }
  return {room:ram.add(0x88).readU32(),actors};
}
let pulseUntil = 0, focusUntil=0, pulseKeys = [], keyHook = null, inputCalls=0, forcedCalls=0;
let inputDevice=null;
let logicalInputHook=null,logicalInputCalls=0;
let debugInputEvent=null;
function inputEventSignal(active){
  const kernel=Process.getModuleByName('kernel32.dll');
  if(!debugInputEvent){
    debugInputEvent=new NativeFunction(kernel.getExportByName('OpenEventW'),'pointer',['uint','int','pointer'],'stdcall')(0x100002,0,Memory.allocUtf16String('Local\\AriaWideDebugInput-'+Process.id));
    if(debugInputEvent.isNull()){debugInputEvent=null;throw Error('Restart through the current quiet launcher: no input guard event');}
  }
  if(!new NativeFunction(kernel.getExportByName(active?'SetEvent':'ResetEvent'),'int',['pointer'],'stdcall')(debugInputEvent))throw Error('Input guard event update failed');
}
let emuMask=0;
let native=null;
const loadedPatches=new Map();
let focusHooks=[];
let positionJob=null;
let entryJob=null,entryResult=null;
let endingJob=null;
let keyboardEnabledBefore=null;
let stateSaves=0,stateLoads=0;
const doorEdits=[];
let blendBefore=null,blendPpu=null;
const states=new Map();
function onFrame(work){return new Promise((resolve,reject)=>{
  let done=false;
  pending.push(()=>{if(done)return;done=true;try{resolve(work());}catch(e){reject(e);}});
  setTimeout(()=>{if(!done){done=true;reject(Error('No GBA frame for diagnostic work'));}},5000);
});}
function stateGlobals(work,preserveSram=true){
  if(!context||base.add(0x2839b4).readU32()!==0)throw Error('No context or unsupported state stream mode');
  const a=base.add(0x149efa4),b=base.add(0x149efa8),oldA=a.readPointer(),oldB=b.readPointer();
  // Private diagnostic fixtures can predate the user's current save slots.
  // Preserve cartridge SRAM across fixture RPCs; real M2 save/load is untouched.
  const sram=context.add(0x48150),oldSram=preserveSram?sram.readByteArray(0x20010):null;
  try{return work();}finally{if(oldSram)sram.writeByteArray(oldSram);a.writePointer(oldA);b.writePointer(oldB);}
}
function freeState(head){new NativeFunction(base.add(0x38c20),'void',['pointer'],'thiscall')(head);}
function stateRecords(head){
  const records=[],seen=new Set();let node=head.readPointer(),total=0;
  while(!node.isNull()){
    if(seen.has(node.toString())||records.length>=4096)throw Error('Invalid state list');seen.add(node.toString());
    const record=node.readPointer(),nameLength=record.add(4).readU32(),size=record.add(12).readU32();
    if(nameLength<1||nameLength>256||size>0x400000||total+size>0x2000000)throw Error('Invalid state record');
    records.push({name:record.readPointer().readCString(nameLength),size,data:record.add(8).readPointer(),offset:total});
    total+=size;node=node.add(4).readPointer();
  }
  if(records.length<20)throw Error('Incomplete emulator state');
  return records;
}
function dump(path, address, size) {
  const f = new File(path, 'wb');
  try { f.write(address.readByteArray(size)); } finally { f.close(); }
}
function viewport(){const m=Process.getModuleByName('d3d9.dll'),fn=m.findExportByName('GetViewport');if(!fn)return null;const out=Memory.alloc(16);new NativeFunction(fn,'void',['pointer'],'mscdecl')(out);return {left:out.readU32(),camera:out.add(4).readS32(),width:out.add(8).readU32(),expanded:!!out.add(12).readU32()};}
function snapshot(prefix, full) {
  if (!context || !Process.findRangeByAddress(context)) throw Error('No live GBA context');
  const bitmap = context.readPointer();
  let width = bitmap.readU32(), height = bitmap.add(4).readU32();
  if (width !== 240 || height !== 160) throw Error('Unexpected video geometry');
  const ppu = context.add(0x138).readPointer();
  const pixels = bitmap.add(0x34).readPointer();
  const pitch = bitmap.add(0x1c).readU32();
  if (pitch<480 || pitch>8192 || bitmap.add(0x18).readU32()!==2)throw Error('Unexpected pixel format: '+pitch+'/'+bitmap.add(0x18).readU32());
  if(pitch>=576){width=288;height=162;}
  const packed=Memory.alloc(width*height*2);
  for(let y=0;y<height;y++)Memory.copy(packed.add(y*width*2),pixels.add(y*pitch),width*2);
  dump(prefix+'.rgb555', packed,width*height*2);
  if (full) {
    dump(prefix+'.ppu', ppu, 0x5f4b8);
    dump(prefix+'.ewram', context.add(0x150), 0x40000);
    dump(prefix+'.iwram', context.add(0x40150), 0x8000);
  }
  const pad=context.add(12).readPointer();
  const ram=context.add(0x150);
  return {width,height,pitch,viewport:viewport(),context:context.toString(),ppu:ppu.toString(),bitmap:bitmap.toString(),romCode:context.add(0x1a0558).readPointer().add(0xac).readCString(4),dispcnt:ppu.add(0x20800).readU16(),gameMode:ram.add(0x10).readU8(),stage:ram.add(0x11).readU8(),playState:ram.add(0x64).readU8(),area:ram.add(0x9e).readU8(),room:ram.add(0x9f).readU8(),cameraX:ram.add(0xa09a).readS16(),cameraY:ram.add(0xa09e).readS16(),playerX:ram.add(0x524).readS32()/65536,playerY:ram.add(0x528).readS32()/65536,pad:pad.add(0x4c4).readU32(),padConfig:Array.from({length:12},(_,i)=>Array.from({length:5},(_,j)=>pad.add((i+13)*20+j*4).readU32())),timestamp:Date.now()};
}
// Exact-build cdecl frame entry. Capture on return, after the emulator finishes rendering.
Interceptor.attach(base.add(0x39f60),{onEnter(args){if(context&&args[0].equals(context))context=null;}});
Interceptor.attach(base.add(0x3a450), {
  onEnter(args) { context = args[0]; },
  onLeave() {
    if(endingJob){
      const ram=context.add(0x150);
      if(Date.now()>endingJob.until)endingJob=null;
      else if(ram.add(0x10).readU8()===20&&ram.add(0x25545).readU8()===2&&(ram.add(0x64).readU8()===10||(ram.add(0x64).readU8()===1&&ram.add(0xa094).readU32()>=0x08000000))){
        // The retail debug event driver now delegates to the same in-game
        // update routine. Resume its normal dispatch so renderer gating is real.
        ram.add(0x10).writeU8(4);ram.add(0x11).writeU8(0);ram.add(0x12).writeU8(0);endingJob=null;
      }
    }
    if(entryJob){
      const ram=context.add(0x150),job=entryJob;
      if(Date.now()>job.until){entryResult={timedOut:true};entryJob=null;}
      else if(ram.add(0x88).readU32()===job.destination&&ram.add(0x64).readU8()===1){
        const cx=ram.add(0xa09a).readS16(),cy=ram.add(0xa09e).readS16();
        ram.add(0x524).writeS32((job.x-cx)*65536);ram.add(0x528).writeS32((job.y-cy)*65536);
        ram.add(0x52c).writeS32(0);ram.add(0x530).writeS32(0);
        entryResult={placed:true,destination:job.destination,x:job.x,y:job.y};entryJob=null;
      }
    }
    if(positionJob){
      const j=positionJob,ram=context.add(0x150);
      const room=ram.add(0x88).readU32();
      if(room!==j.room||Date.now()>j.until){positionJob=null;j.resolve({transitioned:room!==j.room,timedOut:Date.now()>j.until});}
      else if(ram.add(0x64).readU8()===1){
        const cx=ram.add(0xa09a).readS16(),cy=ram.add(0xa09e).readS16();
        const wx=ram.add(0x524).readS32()/65536+cx,wy=ram.add(0x528).readS32()/65536+cy;
        const dx=Math.max(-8,Math.min(8,j.x-wx)),dy=Math.max(-8,Math.min(8,j.y-wy));
        ram.add(0x524).writeS32(Math.round((wx+dx-cx)*65536));ram.add(0x528).writeS32(Math.round((wy+dy-cy)*65536));
        ram.add(0x52c).writeS32(0);ram.add(0x530).writeS32(0);
        if(Math.abs(j.x-wx)<9&&Math.abs(j.y-wy)<9){positionJob=null;j.resolve({reached:true,world:{x:j.x,y:j.y}});}
      }
    }
    const queue=pending; pending=[]; for(const work of queue) work();
  }
});
function consumeDenseFrame(){
    if(denseJob&&denseJob.scan){
      const job=denseJob;
      try{
        const v=viewport(),s=job.scan;job.scan=null;
        let corrections=null;const correctionFn=Process.getModuleByName('d3d9.dll').findExportByName('GetBackgroundCorrections');
        if(correctionFn){const out=Memory.alloc(16);new NativeFunction(correctionFn,'void',['pointer'],'mscdecl')(out);corrections=[0,1,2,3].map(i=>out.add(i*4).readS32());}
        const raster=s.ramCamera+((s.scroll[1]-s.ramCamera+256)&511)-256;
        let cloudCorrections=null;const cloudFn=Process.getModuleByName('d3d9.dll').findExportByName('GetCloudCorrections');
        if(cloudFn){const out=Memory.alloc(512);new NativeFunction(cloudFn,'void',['pointer'],'mscdecl')(out);cloudCorrections=Array.from({length:128},(_,i)=>out.add(i*4).readS32());}
        job.rows.push({...s,viewport:v,corrections,cloudCorrections,rasterCamera:raster,rasterWideCamera:raster-v.left,time:Date.now()});
        Memory.copy(job.buffer.add((job.rows.length-1)*288*162*2),job.frame,288*162*2);
        if(job.rows.length===job.count){
          denseJob=null;armPad(0,0);denseScanHook.detach();denseScanHook=null;
          dump(job.prefix+'.frames.rgb555',job.buffer,job.count*288*162*2);
          if(job.cloudReferences){dump(job.prefix+'.sources.bin',job.sources,job.count*0x20800);dump(job.prefix+'.native-bg3.bin',job.nativeBG3,job.count*160*240*4);}
          if(job.objectReferences)dump(job.prefix+'.ppu.bin',job.objectSources,job.count*0x5f4b8);
          File.writeAllText(job.prefix+'.frames.json',JSON.stringify(job.rows));job.resolve({frames:job.count,bytes:job.count*288*162*2});
        }
      }catch(e){denseJob=null;armPad(0,0);if(denseScanHook){denseScanHook.detach();denseScanHook=null;}job.reject(e);}
    }
}
// Frame RPC return may already be partway through the next GBA raster. Capture
// immediately after native presentation for temporal-blend reference checks.
function installPresentCapture(){if(presentCaptureHook)return;presentCaptureHook=Interceptor.attach(base.add(0x47710),{
  onEnter(){this.target=this.context.ecx;},
  onLeave(){
    if(!context||!this.target.equals(context.add(0x138).readPointer()))return;
    consumeDenseFrame();
    cloudPrevious=cloudActors();
    const queue=pendingPresent;pendingPresent=[];for(const work of queue)work();
  }
});}
// Mid-function input uses the pinned diagnostic DLL, not a Gum listener.
function installInput() {
    if(!logicalInputHook){
      const address=base.add(0x1548c0);
      if(address.readU8()!==0x55||address.add(1).readU16()!==0xec8b)throw Error('Native UI controller signature mismatch');
      const bits={203:0x20,205:0x10,200:0x40,208:0x80,44:1,45:2,28:8,15:4,30:0x400,31:0x800};
      logicalInputHook=Interceptor.attach(address,{onEnter(args){this.pad=args[0].toUInt32();this.out=args[1];},onLeave(){
        if(this.pad<4&&Date.now()<pulseUntil&&Date.now()<focusUntil){const mask=pulseKeys.reduce((m,k)=>m|(bits[k]||0),0);if(mask){this.out.writeU32(this.out.readU32()|mask);logicalInputCalls++;}}
      }});
    }
    const device=base.add(0x2844d4).readPointer();
    if(device.isNull())throw Error('Game keyboard not initialized');
    if(keyHook&&inputDevice&&inputDevice.equals(device))return;
    if(keyHook){keyHook.detach();keyHook=null;Interceptor.flush();}
    inputDevice=device;
    const state=device.readPointer().add(36).readPointer();
    keyHook=Interceptor.attach(state,{
      onEnter(args){this.size=args[0].equals(device)?args[1].toUInt32():0;this.buffer=args[2];if(this.size===256)inputCalls++;},
      onLeave(ret){if(this.size===256){
        // For the whole controller lifetime, isolate collection menus from
        // physical keys typed in other apps, including between our pulses.
        this.buffer.writeByteArray(new Uint8Array(256));
        if(Date.now()<pulseUntil){forcedCalls++;for(const scan of pulseKeys)this.buffer.add(scan).writeU8(128);}
        ret.replace(0);
      }}
    });
}
rpc.exports = {
  romdump(path){return onFrame(()=>{
    if(!context)throw Error('No live context');
    const rom=context.add(0x1a0558).readPointer(),size=context.add(0x1a055c).readU32();
    if(size<0x100000||size>0x2000000||rom.add(0xac).readCString(3)!=='A2C')throw Error('Not a bounded Aria ROM');
    dump(path,rom,size);return {bytes:size,code:rom.add(0xac).readCString(4)};
  });},
  roompointer(area,room){return onFrame(()=>{
    if(!context||!Number.isInteger(area)||area<0||area>=12||!Number.isInteger(room)||room<0||room>=64)throw Error('Invalid room query');
    const rom=context.add(0x1a0558).readPointer(),size=context.add(0x1a055c).readU32(),ram=context.add(0x150);
    if(rom.add(0xac).readCString(4)!=='A2CJ')throw Error('Only verified JP room table');
    function guest(address,n){if(address<0x08000000||address-0x08000000+n>size)throw Error('ROM table outside bounds');return rom.add(address-0x08000000);}
    const table=rom.add(0x198c).readU32(),start=guest(table+area*4,4).readU32(),end=area<11?guest(table+(area+1)*4,4).readU32():table;
    if(end<=start||end-start>256||(end-start)%4||room>=(end-start)/4)throw Error('Room-table signature differs');
    const target=guest(start+room*4,4).readU32(),header=guest(ram.add(0x88).readU32(),36),count=header.add(28).readU16();
    if(count>64)throw Error('Invalid current room doors');
    const doors=Array.from({length:count},(_,i)=>{const d=guest(header.add(24).readU32()+i*16,16);return {i,x:d.add(4).readS8(),y:d.add(5).readS8()};});
    return {target,source:ram.add(0x88).readU32(),doors};
  });},
  denseframes(prefix,count,keys,duration,cloudReferences=false){return new Promise((resolve,reject)=>{
    if(denseJob||!Number.isInteger(count)||count<30||count>180||!Array.isArray(keys)||keys.some(k=>![203,205].includes(k))||duration<100||duration>1800){reject(Error('Invalid dense bounded capture'));return;}
    const module=Process.getModuleByName('d3d9.dll'),getFrame=new NativeFunction(module.getExportByName('GetFrame'),'pointer',[],'mscdecl');
    installPresentCapture();
    denseJob={prefix,count,buffer:Memory.alloc(count*288*162*2),frame:getFrame(),rows:[],scan:null,resolve,reject};
    if(cloudReferences==='objects'){denseJob.objectReferences=true;denseJob.objectSources=Memory.alloc(count*0x5f4b8);}
    if(cloudReferences===true){
      denseJob.cloudReferences=true;denseJob.sources=Memory.alloc(count*0x20800);denseJob.nativeBG3=Memory.alloc(count*160*240*4);
      denseJob.packModule=new CModule('void pack(const unsigned int *source,unsigned int *out){int x;for(x=0;x<240;x++)out[x]=source[x*5+3];}');
      denseJob.pack=new NativeFunction(denseJob.packModule.pack,'void',['pointer','pointer'],'mscdecl');
    }
    denseScanHook=Interceptor.attach(base.add(0x47680),{onEnter(){
      this.captureY=-1;
      if(!denseJob||!context||!this.context.ecx.equals(context.add(0x138).readPointer()))return;
      const y=this.context.edx.toInt32();if(y<0||y>=160)return;
      const ppu=this.context.ecx,ram=context.add(0x150);
      if(y===0){
        if(denseJob.objectReferences)Memory.copy(denseJob.objectSources.add(denseJob.rows.length*0x5f4b8),ppu,0x5f4b8);
        denseJob.scan={ramCamera:ram.add(0xa09a).readS16(),mainFP:ram.add(0xa098).readS32(),bgFP:[1,2,3].map(bg=>ram.add(0xa078+bg*28+4).readS32()),methods:[1,2,3].map(bg=>ram.add(0xa078+bg*28+24).readU8()),scroll:[0,1,2,3].map(bg=>ppu.add(0x21ff8+bg*4).readU16()),area:ram.add(0x9e).readU8(),room:ram.add(0x9f).readU8()};
        denseJob.scan.cloudNow=cloudActors();denseJob.scan.cloudPrevious=cloudPrevious;
        denseJob.scan.cloudOam=[];
        for(let o=0;o<128;o++){
          const a0=ppu.add(0x20000+o*8).readU16(),a1=ppu.add(0x20002+o*8).readU16(),a2=ppu.add(0x20004+o*8).readU16();
          if((a0&0xff00)===0x4400&&(a1&0xc000)===0x8000&&(a2&0xc00)===0xc00)denseJob.scan.cloudOam.push({o,a0,a1,a2});
        }
        if(denseJob.cloudReferences){
          Memory.copy(denseJob.sources.add(denseJob.rows.length*0x20800),ppu,0x20800);
          Object.assign(denseJob.scan,{control:[0,1,2,3].map(bg=>ppu.add(0x21ff0+bg*2).readU16()),flags:ppu.add(0x22048).readU16(),blendMode:ppu.add(0x2205c).readU32(),renderEnabled:ppu.add(0x22058).readU32(),lineScroll:[],backdrop:ppu.add(0x20400).readU16()});
        }
      }
      if(denseJob.cloudReferences&&denseJob.scan){denseJob.scan.lineScroll[y]=[0,1,2,3,4,5,6,7].map(i=>ppu.add(0x21ff8+i*2).readU16());this.captureY=y;this.ppu=ppu;}
    },onLeave(){
      if(this.captureY>=0&&denseJob&&denseJob.cloudReferences&&denseJob.scan)denseJob.pack(this.ppu.add(0x20c00),denseJob.nativeBG3.add((denseJob.rows.length*160+this.captureY)*240*4));
    }});
    armPad(keys.reduce((m,k)=>m|(k===203?32:16),0),duration);
    setTimeout(()=>{if(denseJob&&denseJob.resolve===resolve){denseJob=null;armPad(0,0);if(denseScanHook){denseScanHook.detach();denseScanHook=null;}reject(Error('Dense capture timed out'));}},8000);
  });},
  debugenemynotice(nameId=605,notificationKind=2){return onFrame(()=>{
    if(notificationKind===null)notificationKind=2;
    const ram=context.add(0x150),rom=context.add(0x1a0558).readPointer(),ppu=context.add(0x138).readPointer();
    if(rom.add(0xac).readCString(4)!=='A2CJ'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1||(ppu.add(0x21ff0).readU16()&0xfffc)!==0x1c00)throw Error('Not verified native JP gameplay HUD');
    if(!Number.isInteger(nameId)||nameId<605||nameId>716)throw Error('Outside native enemy-name string IDs');
    if(![1,2].includes(notificationKind))throw Error('Unknown native notification queue');
    if(ram.add(0x42c).readU32()&0x03000200)throw Error('A native modal HUD is active');
    // Diagnostic-only: the native enemy notification driver (US reference
    // 0800EA98 -> 0800EFD4 -> 0800DE4C) consumes this existing request queue.
    // No custom tiles, font, enemy HP or player inventory are written.
    ram.add(0x420).writeU16(nameId);ram.add(0x423).writeU8(notificationKind);
    return {debugOnly:true,nativeEnemyNameRequest:notificationKind===2,nativeItemLayoutRequest:notificationKind===1,nameId};
  });},
  debugsoullayout(firstRow=1){return onFrame(()=>{
    if(firstRow===null)firstRow=1;if(![1,3].includes(firstRow))throw Error('Unknown soul layout row');
    const ram=context.add(0x150),ppu=context.add(0x138).readPointer(),map=ppu.add(0xe000);
    if(context.add(0x1a0558).readPointer().add(0xac).readCString(4)!=='A2CJ'||ram.add(0x64).readU8()!==1||(ppu.add(0x21ff0).readU16()&0xfffc)!==0x1c00||ram.add(0x422).readU8()<30)throw Error('No verified notification layout to move');
    const cells=Array.from({length:96},(_,i)=>map.add(18*64+i*2).readU16());
    if(!cells.includes(0xe220))throw Error('Native notification frame missing');
    for(let i=0;i<96;i++)if(cells[i]){
      let tile=cells[i];if(tile===0xe221)tile=0xe234;else if(tile===0xe222)tile=0xe235;else if(tile===0xe241)tile=0xe254;else if(tile===0xe242)tile=0xe255;
      map.add(firstRow*64+i*2).writeU16(tile);
    }
    for(let i=0;i<96;i++)map.add(18*64+i*2).writeU16(0);
    return {debugOnly:true,syntheticSoulTileLayout:true,inventoryChanged:false};
  });},
  viewport,
  romcode(){if(!context)return null;return context.add(0x1a0558).readPointer().add(0xac).readCString(4);},
  bossrushmenu(){return onFrame(()=>{
    const ram=context.add(0x150),rom=context.add(0x1a0558).readPointer();
    if(rom.add(0xac).readCString(4)!=='A2CJ'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1||rom.add(0x524+8*4).readU32()!==0x08000596||rom.add(0x7d60).readU32()!==0x084fb0b4)throw Error('Not verified JP Boss Rush menu source');
    const before={mode:ram.add(0x10).readU8(),playState:ram.add(0x64).readU8(),header:ram.add(0x88).readU32()};
    // Diagnostic entry only. Native mode 8 performs selection, cleanup,
    // character presets, Boss Rush flags, and the original room load.
    ram.add(0x3cc).writeU32(0);ram.add(0x64).writeU8(0);ram.add(0x65).writeU8(0);
    ram.add(0x10).writeU8(8);ram.add(0x11).writeU8(0);ram.add(0x12).writeU8(0);
    return {debugOnly:true,before,targetHeader:0x084fb0b4};
  });},
  nativeendingrequest(kind){return onFrame(()=>{
    const selected={bad:16,true:17,julius:18}[kind],rom=context.add(0x1a0558).readPointer(),ram=context.add(0x150);
    if(!selected||rom.add(0xac).readCString(4)!=='A2CJ'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1||rom.add(0x37c00).readU32()!==0x25544)throw Error('Not verified JP scripted transition source');
    const table=rom.add(0x37bf8).readU32(),targetHeader=rom.add(table-0x08000000+(selected-3)*4).readU32();
    const before={flags:ram.add(0x42c).readU32(),room:ram.add(0x88).readU32()};
    // Populate the native 08011138 request fields and enter the 08010cc4
    // transition state. Unlike a doorway this supports zero-door scenes.
    ram.add(0x3f8).writeU32(targetHeader);for(const off of [0x3fc,0x3fe,0x400,0x402])ram.add(off).writeU16(0);
    ram.add(0x42c).writeU32((before.flags&~0xe000)|({bad:0x2000,true:0x4000,julius:0x8000}[kind])|0x800000);
    ram.add(0xa074).writeU8((ram.add(0xa074).readU8()&~2)|1);ram.add(0x64).writeU8(8);ram.add(0x65).writeU8(0);
    endingJob=null;return {debugOnly:true,nativeTransition:true,targetHeader,before};
  });},
  nativechaosending(){return onFrame(()=>{
    const rom=context.add(0x1a0558).readPointer(),ram=context.add(0x150);
    if(rom.add(0xac).readCString(4)!=='A2CJ'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1||rom.add(0xbce8).readU32()!==0x084f9fa4||rom.add(0xbc18).readU32()!==0x42c)throw Error('Not verified JP native ending source');
    const before={flags:ram.add(0x42c).readU32(),room:ram.add(0x88).readU32()};
    // Diagnostic trigger only: native play-state 2 performs its own fade,
    // cleanup, scripted-room request and state-8 transition (JP 0800bb94).
    ram.add(0x42c).writeU32(before.flags|0x200000);ram.add(0x64).writeU8(2);ram.add(0x65).writeU8(0);
    endingJob=null;return {debugOnly:true,nativeTransition:true,targetHeader:0x084f9fa4,before};
  });},
  debugending(kind){return onFrame(()=>{
    const selected={bad:16,true:17,julius:18,chaos:20}[kind];
    const rom=context.add(0x1a0558).readPointer(),ram=context.add(0x150);
    if(!selected||rom.add(0xac).readCString(4)!=='A2CJ'||![1,2,4].includes(ram.add(0x10).readU8()))throw Error('Not a verified ending test source');
    if(rom.add(0x524+20*4).readU32()!==0x080005ea||rom.add(0x37c00).readU32()!==0x25544||rom.add(0xe0dbc+4).readU32()!==17)throw Error('JP event-driver signatures differ');
    const before={flags:ram.add(0x42c).readU32(),previousRoom:ram.add(0x3cc).readU32(),substage:ram.add(0x65).readU8()};
    const table=rom.add(0x37bf8).readU32();
    const targetHeader=rom.add(table-0x08000000+(selected-3)*4).readU32();
    ram.add(0x42c).writeU32(0);ram.add(0x3cc).writeU32(0);
    ram.add(0x25544).writeU8(selected);ram.add(0x25545).writeU8(0);ram.add(0x25546).writeU8(0);
    // Entering from an existing save can retain a menu's substage (e.g. 7),
    // which the in-game room loader's state-zero switch cannot advance.
    ram.add(0x65).writeU8(0);
    ram.add(0x10).writeU8(20);ram.add(0x11).writeU8(0);ram.add(0x12).writeU8(0);
    endingJob={until:Date.now()+120000};return {debugOnly:true,event:selected,targetHeader,before,normalDispatchAfterInitialization:true};
  });},
  endingstatus(){if(!context)return null;const ram=context.add(0x150);return {mode:ram.add(0x10).readU8(),playState:ram.add(0x64).readU8(),substage:ram.add(0x65).readU8(),driver:ram.add(0x25544).readU8(),driverStage:ram.add(0x25545).readU8(),roomPointer:ram.add(0x88).readU32(),eventFlags:ram.add(0x42c).readU32()};},
  patchstatus(){
    const modules=Process.enumerateModules().filter(m=>/^realtime-v\d+\.dll$/i.test(m.name));modules.push(Process.getModuleByName('d3d9.dll'));
    return {modules:modules.map(m=>({name:m.name,installed:m.findExportByName('IsInstalled')?new NativeFunction(m.getExportByName('IsInstalled'),'int',[],'mscdecl')():null})),entries:[0x47680,0x47710,0x39ab0].map(rva=>{
      const a=base.add(rva),jump=a.readU8()===0xe9?a.add(5).add(a.add(1).readS32()):null;return {rva,bytes:Array.from(new Uint8Array(a.readByteArray(8))),target:jump?jump.toString():null,owner:jump?Process.findModuleByAddress(jump)?.name:null};
    })};
  },
  lifecycle(){
    const modules=Process.enumerateModules().filter(m=>/^realtime-v\d+\.dll$/i.test(m.name)).sort((a,b)=>parseInt(b.name.match(/\d+/)[0])-parseInt(a.name.match(/\d+/)[0]));
    modules.push(Process.getModuleByName('d3d9.dll'));
    for(const m of modules){const check=m.findExportByName('IsInstalled'),fn=m.findExportByName('GetLifecycle');
      if(!fn||check&&!new NativeFunction(check,'int',[],'mscdecl')())continue;
      const out=Memory.alloc(24);new NativeFunction(fn,'void',['pointer'],'mscdecl')(out);
      return {module:m.name,contextChanges:out.readU32(),destroyed:out.add(4).readU32(),activeContext:out.add(8).readU32(),activePpu:out.add(12).readU32(),running:out.add(16).readU32(),hooksReady:out.add(20).readU32()};
    }return {installed:false};
  },
  initfailuretest(path){return onFrame(()=>{
    if(presentCaptureHook){presentCaptureHook.detach();presentCaptureHook=null;Interceptor.flush();}
    const module=Process.getModuleByName('d3d9.dll');
    const install=new NativeFunction(module.getExportByName('Install'),'int',['pointer'],'mscdecl');
    const uninstall=new NativeFunction(module.getExportByName('Uninstall'),'int',[],'mscdecl');
    if(uninstall()!==0)throw Error('Could not suspend active patch');
    let result,unchanged=false,reinstalled;
    try{
      const addresses=[0x47680,0x47710,0x39ab0,0x406c0,0x40610,0x39f60,0x153e80,0x38c20,0xe570];
      const before=addresses.map(a=>new Uint8Array(base.add(a).readByteArray(16)));
      const probe=Module.load(path);
      result=new NativeFunction(probe.getExportByName('Install'),'int',['pointer'],'mscdecl')(context);
      unchanged=addresses.every((a,i)=>{
        const after=new Uint8Array(base.add(a).readByteArray(16));return after.every((v,j)=>v===before[i][j]);
      });
    }finally{reinstalled=install(context);}
    return {result,originalCodeUnchanged:unchanged,reinstalled};
  });},
  debugentry(destination,x,y){
    if(!Number.isInteger(destination)||!Number.isInteger(x)||!Number.isInteger(y)||x<16||x>2000||y<48||y>2000)throw Error('Invalid diagnostic entry');
    entryJob={destination,x,y,until:Date.now()+5000};entryResult=null;return {armed:true};
  },
  debugentryresult(){return entryResult;},
  debugdoor(index,destination){return onFrame(()=>{
    const ram=context.add(0x150),rom=context.add(0x1a0558).readPointer(),size=context.add(0x1a055c).readU32();
    if(rom.add(0xac).readCString(4)!=='A2CJ'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1)throw Error('Not verified JP/translated Aria gameplay');
    const current=ram.add(0x88).readU32();
    function guest(address,length){if(address<0x08000000||address-0x08000000+length>size)throw Error('ROM address out of bounds');return rom.add(address-0x08000000);}
    const header=guest(current,36),count=header.add(28).readU16();
    if(!Number.isInteger(index)||index<0||index>=count||count>64||!Number.isInteger(destination))throw Error('Invalid diagnostic door');
    const target=guest(destination,36),layers=guest(target.add(8).readU32(),12),meta=guest(layers.add(8).readU32(),16);
    if(meta.readU8()<1||meta.readU8()>64||meta.add(1).readU8()<1||meta.add(1).readU8()>64)throw Error('Invalid destination metadata');
    const address=guest(header.add(24).readU32()+index*16,16),old=address.readU32();
    doorEdits.push({address,old,rom});address.writeU32(destination);
    return {debugOnly:true,source:current,index,old,destination,cell:[address.add(4).readS8(),address.add(5).readS8()]};
  });},
  restoredoors(){return onFrame(()=>{
    for(const edit of doorEdits){if(!context.add(0x1a0558).readPointer().equals(edit.rom))throw Error('ROM identity changed before restoration');edit.address.writeU32(edit.old);}
    const count=doorEdits.length;doorEdits.length=0;return {restored:count};
  });},
  statewatch(){
    stateSaves=stateLoads=0;
    Interceptor.attach(base.add(0x406c0),{onEnter(){if(context&&this.context.ecx.equals(context))stateSaves++;}});
    Interceptor.attach(base.add(0x40610),{onEnter(){if(context&&this.context.ecx.equals(context))stateLoads++;}});
    return {watching:true};
  },
  statecounts(){return {saves:stateSaves,loads:stateLoads};},
  debugblend(mode){return onFrame(()=>{
    if(!Number.isInteger(mode)||mode<0||mode>3)throw Error('Invalid blend mode');
    const ppu=context.add(0x138).readPointer();
    if(blendBefore===null){blendBefore=ppu.add(0x2205c).readU32();blendPpu=ppu;}
    ppu.add(0x2205c).writeU32(mode);return {mode,previous:blendBefore};
  });},
  statecompare(a,b){return onFrame(()=>{
    if(!states.has(a)||!states.has(b))throw Error('Unknown state');
    const aa=stateRecords(states.get(a)),bb=stateRecords(states.get(b)),changes=[];
    for(const r of aa){const s=bb.find(x=>x.name===r.name);
      if(!s||s.size!==r.size){changes.push({name:r.name,lengthChanged:true});continue;}
      const x=new Uint8Array(r.data.readByteArray(r.size)),y=new Uint8Array(s.data.readByteArray(s.size));
      let count=0;for(let i=0;i<x.length;i++)if(x[i]!==y[i])count++;
      if(count)changes.push({name:r.name,bytes:count});
    }
    return {records:aa.length,changes};
  });},
  statereloadsave(name,copy){return onFrame(()=>stateGlobals(()=>{
    if(!states.has(name)||states.has(copy))throw Error('Invalid state names');
    new NativeFunction(base.add(0x3a260),'void',['pointer','pointer'],'mscdecl')(context,states.get(name));
    const head=new NativeFunction(base.add(0x1ec6b1),'pointer',['uint'],'mscdecl')(4);
    if(head.isNull())throw Error('Allocation failed');head.writePointer(ptr(0));
    try{new NativeFunction(base.add(0x3a240),'void',['pointer','pointer'],'mscdecl')(context,head);stateRecords(head);states.set(copy,head);return {loadedAndSaved:true};}
    catch(e){freeState(head);throw e;}
  }));},
  stateimport(name,prefix){return onFrame(()=>{
    if(states.has(name))throw Error('State name already exists');
    const records=JSON.parse(File.readAllText(prefix+'.state.json')),data=File.readAllBytes(prefix+'.state.bin');
    if(!Array.isArray(records)||records.length<20||records.length>4096||data.byteLength>0x2000000)throw Error('Invalid private fixture');
    const malloc=new NativeFunction(base.add(0x1ec6b1),'pointer',['uint'],'mscdecl');
    function alloc(size){const p=malloc(size);if(p.isNull())throw Error('State allocation failed');return p;}
    const head=alloc(4);head.writePointer(ptr(0));let link=head;
    try{
      for(const r of records){
        if(typeof r.name!=='string'||!/^[\x20-\x7e]{1,256}$/.test(r.name)||!Number.isInteger(r.size)||r.size<0||r.size>0x400000||!Number.isInteger(r.offset)||r.offset<0||r.offset+r.size>data.byteLength)throw Error('Invalid fixture record');
        const node=alloc(8),record=alloc(16),tag=alloc(r.name.length+1),value=alloc(Math.max(1,r.size));
        tag.writeUtf8String(r.name);if(r.size)value.writeByteArray(data.slice(r.offset,r.offset+r.size));
        record.writePointer(tag);record.add(4).writeU32(r.name.length);record.add(8).writePointer(value);record.add(12).writeU32(r.size);
        node.writePointer(record);node.add(4).writePointer(ptr(0));link.writePointer(node);link=node.add(4);
      }
      stateRecords(head);states.set(name,head);return {imported:true,records:records.length};
    }catch(e){freeState(head);throw e;}
  });},
  statesave(name,prefix=null){return onFrame(()=>stateGlobals(()=>{
    if(states.has(name))throw Error('State name already exists');
    const head=new NativeFunction(base.add(0x1ec6b1),'pointer',['uint'],'mscdecl')(4);
    if(head.isNull())throw Error('State allocation failed');head.writePointer(ptr(0));
    try{
      new NativeFunction(base.add(0x3a240),'void',['pointer','pointer'],'mscdecl')(context,head);
      const records=stateRecords(head);
      if(prefix){
        const f=new File(prefix+'.state.bin','wb');try{for(const r of records)f.write(r.data.readByteArray(r.size));}finally{f.close();}
        const json=new File(prefix+'.state.json','w');try{json.write(JSON.stringify(records.map(({name,size,offset})=>({name,size,offset}))));}finally{json.close();}
      }
      states.set(name,head);
      const ram=context.add(0x150);
      return {name,records:records.length,bytes:records.reduce((n,r)=>n+r.size,0),tags:records.map(r=>r.name),room:ram.add(0x9f).readU8(),x:ram.add(0x524).readS32()/65536,y:ram.add(0x528).readS32()/65536};
    }catch(e){freeState(head);throw e;}
  }));},
  stateload(name,preserveSram=true){preserveSram=preserveSram!==false;return onFrame(()=>stateGlobals(()=>{
    const head=states.get(name);if(!head)throw Error('Unknown state');stateRecords(head);
    new NativeFunction(base.add(0x3a260),'void',['pointer','pointer'],'mscdecl')(context,head);
    const ram=context.add(0x150);return {loaded:true,preserveSram,gameMode:ram.add(0x10).readU8(),playState:ram.add(0x64).readU8(),room:ram.add(0x9f).readU8(),x:ram.add(0x524).readS32()/65536,y:ram.add(0x528).readS32()/65536};
  },preserveSram));},
  cartdump(path){return onFrame(()=>{dump(path,context.add(0x48150),0x20010);return {bytes:0x20010};});},
  stats(){
    const modules=Process.enumerateModules().filter(m=>/^realtime-v\d+\.dll$/i.test(m.name)).sort((a,b)=>parseInt(b.name.match(/\d+/)[0])-parseInt(a.name.match(/\d+/)[0]));
    modules.push(Process.getModuleByName('d3d9.dll'));
    for(const m of modules){
      const check=m.findExportByName('IsInstalled');
      if(check&&!new NativeFunction(check,'int',[],'mscdecl')())continue;
      const counters=m.findExportByName('GetCounters');if(!counters)continue;
      const out=Memory.alloc(12);new NativeFunction(counters,'void',['pointer'],'mscdecl')(out);
      return {module:m.name,frames:out.readU32(),lines:out.add(4).readU32(),unknownModes:out.add(8).readU32(),worker:context?context.add(0x1a05bc).readU32():null};
    }
    return {installed:false};
  },
  hotreplace(path){return new Promise((resolve,reject)=>{
    let done=false;
    pending.push(()=>{if(done)return;done=true;try{
      if(presentCaptureHook){presentCaptureHook.detach();presentCaptureHook=null;Interceptor.flush();}
      for(const m of Process.enumerateModules().filter(m=>/^realtime-v\d+\.dll$/i.test(m.name)))loadedPatches.set(m.name,m);
      const proxy=Process.getModuleByName('d3d9.dll');loadedPatches.set(proxy.name,proxy);
      // Retain Module.load results ourselves: the registry may not list a newly
      // loaded DLL until the current script yields. Reconcile every resident
      // owner before re-enabling a previously loaded patch module.
      for(const old of loadedPatches.values()){
        const check=old.findExportByName('IsInstalled');if(check&&!new NativeFunction(check,'int',[],'mscdecl')())continue;
        const result=new NativeFunction(old.getExportByName('Uninstall'),'int',[],'mscdecl')();if(result!==0)throw Error('Old uninstall '+result);
      }
      const module=Module.load(path);
      loadedPatches.set(module.name,module);
      const installed=new NativeFunction(module.getExportByName('Install'),'int',['pointer'],'mscdecl')(context);
      if(installed!==0)throw Error('New install '+installed+'; restart required');
      resolve({installed:true,module:module.name,retainedUntilProcessExit:true});
    }catch(e){reject(e);}});
    setTimeout(()=>{if(!done){done=true;reject(Error('No frame for hot replacement'));}},5000);
  });},
  debugmove(x,y){
    const ram=context.add(0x150),rom=context.add(0x1a0558).readPointer();
    if(rom.add(0xac).readCString(3)!=='A2C'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1)throw Error('Not ordinary Aria gameplay');
    if(!Number.isInteger(x)||!Number.isInteger(y)||x<16||x>2000||y<48||y>2000)throw Error('Invalid coordinate');
    if(positionJob)throw Error('Position job already active');
    return new Promise(resolve=>{
      const job={x,y,room:ram.add(0x88).readU32(),until:Date.now()+6000,resolve};positionJob=job;
      setTimeout(()=>{if(positionJob===job){positionJob=null;resolve({timedOut:true});}},6500);
    });
  },
  debugposition(x,y){return new Promise((resolve,reject)=>{
    pending.push(()=>{try{
      const ram=context.add(0x150),rom=context.add(0x1a0558).readPointer();
      if(rom.add(0xac).readCString(3)!=='A2C'||ram.add(0x10).readU8()!==4||ram.add(0x64).readU8()!==1)throw Error('Not ordinary Aria gameplay');
      if(!Number.isInteger(x)||!Number.isInteger(y)||x<0||x>2000||y<0||y>2000)throw Error('Invalid diagnostic coordinate');
      const cx=ram.add(0xa09a).readS16(),cy=ram.add(0xa09e).readS16();
      const old={x:ram.add(0x524).readS32()/65536+cx,y:ram.add(0x528).readS32()/65536+cy};
      ram.add(0x524).writeS32((x-cx)*65536);ram.add(0x528).writeS32((y-cy)*65536);
      ram.add(0x52c).writeS32(0);ram.add(0x530).writeS32(0);
      resolve({old,newWorld:{x,y},debugOnly:true});
    }catch(e){reject(e);}});
  });},
  softreset(){
    emuMask=3;armPad(3,200);pulseUntil=Date.now()+800;
    return new Promise(resolve=>{
      setTimeout(()=>{emuMask=15;armPad(15,400);},200);
      setTimeout(()=>{emuMask=0;armPad(0,0);pulseUntil=0;resolve({released:true});},600);
    });
  },
  uipulse(keys,duration,hwnd){
    if(duration<20||duration>3000)throw Error('Invalid pulse duration');
    if(!focusHooks.length){
      const user=Process.getModuleByName('user32.dll');
      for(const name of ['GetForegroundWindow','GetFocus'])focusHooks.push(Interceptor.attach(user.getExportByName(name),{onLeave(ret){if(Date.now()<focusUntil)ret.replace(ptr(hwnd));}}));
    }
    installInput();
    inputEventSignal(true);
    const enabled=base.add(0x283a8f);keyboardEnabledBefore=enabled.readU8();enabled.writeU8(1);
    pulseKeys=keys;pulseUntil=Date.now()+duration;focusUntil=pulseUntil+1000;const counts=padCounts(),start=counts.input,forced=counts.forced,logical=logicalInputCalls;
    return new Promise(resolve=>setTimeout(()=>{pulseUntil=0;focusUntil=0;pulseKeys=[];inputEventSignal(false);
      if(keyboardEnabledBefore!==null){enabled.writeU8(keyboardEnabledBefore);keyboardEnabledBefore=null;}
      const now=padCounts();resolve({released:true,inputCalls:now.input-start,forcedCalls:now.forced-forced,logicalInputCalls:logicalInputCalls-logical,device:inputDevice.toString()});},duration+1100));
  },
  install(dllPath){
    if(native)throw Error('Native probe already loaded');
    const module=Module.load(dllPath);
    native={module,uninstall:new NativeFunction(module.getExportByName('Uninstall'),'int',[],'mscdecl'),frame:new NativeFunction(module.getExportByName('GetFrame'),'pointer',[],'mscdecl'),counters:new NativeFunction(module.getExportByName('GetCounters'),'void',['pointer'],'mscdecl')};
    const result=new NativeFunction(module.getExportByName('Install'),'int',['pointer'],'mscdecl')(context);
    if(result!==0)throw Error('Install failed '+result);
    return {installed:true};
  },
  cleanup(){
    if(denseScanHook){denseScanHook.detach();denseScanHook=null;}denseJob=null;
    emuMask=0;armPad(0,0);pulseUntil=0;focusUntil=0;entryJob=null;endingJob=null;
    if(debugInputEvent){inputEventSignal(false);const kernel=Process.getModuleByName('kernel32.dll');new NativeFunction(kernel.getExportByName('CloseHandle'),'int',['pointer'],'stdcall')(debugInputEvent);debugInputEvent=null;}
    if(keyboardEnabledBefore!==null){base.add(0x283a8f).writeU8(keyboardEnabledBefore);keyboardEnabledBefore=null;}
    if(blendBefore!==null){blendPpu.add(0x2205c).writeU32(blendBefore);blendBefore=null;}
    for(const edit of doorEdits){if(!context.add(0x1a0558).readPointer().equals(edit.rom))throw Error('Cannot restore diagnostic door after ROM replacement');edit.address.writeU32(edit.old);}doorEdits.length=0;
    for(const head of states.values())freeState(head);states.clear();
    if(native){const result=native.uninstall();native=null;return result;}return 0;
  },
  capturewide(prefix){return new Promise((resolve,reject)=>{
    pending.push(()=>{try{if(!native)throw Error('Not installed');const counters=Memory.alloc(12);native.counters(counters);dump(prefix+'.rgb555',native.frame(),288*162*2);resolve({width:288,height:162,frames:counters.readU32(),lines:counters.add(4).readU32(),unknownModes:counters.add(8).readU32()});}catch(e){reject(e);}});
  });},
  render(prefix,dllPath,objectsOnly=false){return new Promise((resolve,reject)=>{
    pending.push(()=>{try{
      const module=Module.load(dllPath);
      const render=new NativeFunction(module.getExportByName(objectsOnly?'RenderObjects':'RenderSnapshot'),'int',['uint','pointer','pointer','int'],'mscdecl');
      const ppu=context.add(0x138).readPointer();
      const source=Memory.alloc(0x5f4b8);Memory.copy(source,ppu,0x5f4b8);
      const output=Memory.alloc(240*160*2);
      for(const shift of [0,-24,24]){
        const result=render(base.toUInt32(),source,output,shift);
        if(result!==0)throw Error('Render result '+result);
        dump(prefix+'.shift'+shift+'.rgb555',output,240*160*2);
      }
      resolve({rendered:true});
    }catch(e){reject(e);}});
  });},
  renderfile(prefix,dllPath,sourcePath,exportName='RenderObjects'){return onFrame(()=>{
    // Frida appends a null binary payload to RPC calls without one; that
    // occupies an omitted optional argument rather than being undefined.
    if(exportName===null)exportName='RenderObjects';
    const bytes=File.readAllBytes(sourcePath);if(bytes.byteLength!==0x5f4b8)throw Error('Invalid PPU fixture');
    const module=Module.load(dllPath),source=Memory.alloc(0x5f4b8),output=Memory.alloc(240*160*2);source.writeByteArray(bytes);
    if(!['RenderObjects','RenderSnapshot'].includes(exportName))throw Error('Invalid reference export');
    const render=new NativeFunction(module.getExportByName(exportName),'int',['uint','pointer','pointer','int'],'mscdecl');
    for(const shift of [-48,-24,0,24,48]){const result=render(base.toUInt32(),source,output,shift);if(result)throw Error('Reference render '+result);dump(prefix+'.shift'+shift+'.rgb555',output,240*160*2);}
    return {rendered:true};
  });},
  status(){return {base:base.toString(),paused:base.add(0x284bd5).readU8(),deviceLost:base.add(0x284f6f).readU8(),context:context ? context.toString():null,gameMode:context?context.add(0x160).readU8():null,stage:context?context.add(0x161).readU8():null};},
  capture(prefix,full=false){return new Promise((resolve,reject)=>{
    let done=false;
    pending.push(()=>{if(done)return;done=true;try{resolve(snapshot(prefix,full));}catch(e){reject(e);}});
    setTimeout(()=>{if(!done){done=true;reject(Error('No GBA frame within 5 seconds'));}},5000);
  });},
  capturepresent(prefix,full=false){return new Promise((resolve,reject)=>{
    installPresentCapture();
    let done=false;pendingPresent.push(()=>{if(done)return;done=true;try{resolve(snapshot(prefix,full));}catch(e){reject(e);}});
    setTimeout(()=>{if(!done){done=true;reject(Error('No native present within 5 seconds'));}},5000);
  });},
  capturescanpresent(prefix,full=false){return new Promise((resolve,reject)=>{
    // OAM may be rewritten in VBlank before Present. Retain the OAM that
    // actually fed this raster, rather than comparing next-frame objects.
    installPresentCapture();
    if(!scanReferenceHook)scanReferenceHook=Interceptor.attach(base.add(0x47680),{onEnter(){
      if(!context||this.context.edx.toInt32()!==0||!this.context.ecx.equals(context.add(0x138).readPointer()))return;
      const jobs=scanReferences;scanReferences=[];for(const job of jobs)job(this.context.ecx);
    }});
    let done=false;scanReferences.push(ppu=>{if(done)return;const source=Memory.alloc(0x5f4b8);Memory.copy(source,ppu,0x5f4b8);
      pendingPresent.push(()=>{if(done)return;done=true;try{const meta=snapshot(prefix,full);dump(prefix+'.scan.ppu',source,0x5f4b8);resolve(meta);}catch(e){reject(e);}});
    });
    setTimeout(()=>{if(!done){done=true;reject(Error('No raster reference within 5 seconds'));}},5000);
  });},
  pulse(keys,duration){
    if(!Array.isArray(keys)||keys.some(k=>!Number.isInteger(k)||k<0||k>255)||duration<20||duration>3000)throw Error('Invalid bounded key pulse');
    const gba={44:1,45:2,28:8,15:4,200:64,208:128,203:32,205:16,30:512,31:256};
    emuMask=keys.reduce((m,k)=>m|(gba[k]||0),0);armPad(emuMask,duration);pulseUntil=Date.now()+duration;const counts=padCounts(),start=counts.input,forced=counts.forced;
    return new Promise(resolve=>setTimeout(()=>{pulseUntil=0;emuMask=0;armPad(0,0);const now=padCounts();resolve({released:true,inputCalls:now.input-start,forcedCalls:now.forced-forced});},duration+100));
  }
};
