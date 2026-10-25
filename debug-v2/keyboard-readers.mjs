import * as frida from 'frida';
const session=await frida.attach(Number(process.argv[2]));
const script=await session.createScript(`const base=Process.getModuleByName('game.exe').base,device=base.add(0x2844d4).readPointer(),counts={};Interceptor.attach(device.readPointer().add(36).readPointer(),{onEnter(args){if(args[0].equals(device)&&args[1].toUInt32()===256){const key=this.returnAddress.sub(base).toString();counts[key]=(counts[key]||0)+1;}}});setTimeout(()=>send(counts),1200);`);
try{const result=await new Promise(async resolve=>{script.message.connect(m=>{if(m.type==='send')resolve(m.payload);});await script.load();});process.stdout.write(JSON.stringify(result)+'\n');}finally{await script.unload();await session.detach();}
