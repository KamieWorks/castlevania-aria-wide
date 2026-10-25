// Process-owned D3D9 surface readback. No window changes or global input.
import * as frida from 'frida';
import fs from 'node:fs';
const session=await frida.attach(Number(process.argv[2]));
const destination=process.argv[3];
const source=`
const base=Process.getModuleByName('game.exe').base;
function method(p,index,ret,args){return new NativeFunction(p.readPointer().add(index*4).readPointer(),ret,['pointer',...args],'stdcall');}
function hr(value,label){if(value<0)throw Error(label+': '+(value>>>0).toString(16));}
let done=false;
Interceptor.attach(base.add(0x16de60),{onEnter(){
 if(done)return;done=true;let src=ptr(0),dst=ptr(0),locked=false;
 try{
  const device=this.context.ecx.add(8).readPointer(),out=Memory.alloc(4);out.writePointer(ptr(0));
  hr(method(device,18,'int',['uint','uint','int','pointer'])(device,0,0,0,out),'GetBackBuffer');src=out.readPointer();
  const desc=Memory.alloc(32);hr(method(src,12,'int',['pointer'])(src,desc),'GetDesc');
  const format=desc.readU32(),width=desc.add(24).readU32(),height=desc.add(28).readU32();
  if(![21,22].includes(format)||width<240||width>8192||height<160||height>8192||desc.add(16).readU32()!==0)throw Error('Unsupported backbuffer format/size/sampling');
  out.writePointer(ptr(0));hr(method(device,36,'int',['uint','uint','int','int','pointer','pointer'])(device,width,height,format,2,out,ptr(0)),'CreateOffscreenPlainSurface');dst=out.readPointer();
  hr(method(device,32,'int',['pointer','pointer'])(device,src,dst),'GetRenderTargetData');
  const rectangle=Memory.alloc(8);hr(method(dst,13,'int',['pointer','pointer','uint'])(dst,rectangle,ptr(0),16),'LockRect');locked=true;
  const pitch=rectangle.readS32(),bits=rectangle.add(4).readPointer();if(pitch<width*4||pitch>65536)throw Error('Unexpected pitch');
  const file=new File(${JSON.stringify(destination)},'wb');try{for(let y=0;y<height;y++)file.write(bits.add(y*pitch).readByteArray(width*4));}finally{file.close();}
  send({width,height,format,bytes:width*height*4});
 }catch(e){send({error:String(e)});}
 finally{if(locked)method(dst,14,'int',[])(dst);if(!dst.isNull())method(dst,2,'uint',[])(dst);if(!src.isNull())method(src,2,'uint',[])(src);}
}});
`;
const script=await session.createScript(source);
try{
 const result=await new Promise(async(resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('No native Present within 10 seconds')),10000);
  script.message.connect(m=>{if(m.type==='send'){clearTimeout(timer);resolve(m.payload);}else if(m.type==='error'){clearTimeout(timer);reject(Error(m.stack));}});
  try{await script.load();}catch(e){clearTimeout(timer);reject(e);}
 });
 process.stdout.write(JSON.stringify(result)+'\n');if(result.error)process.exitCode=1;
}finally{await script.unload();await session.detach();}
