// Bounded diagnostic pulse at the verified native controller-output boundary.
import * as frida from 'frida';
const pid=Number(process.argv[2]),mask=Number(process.argv[3]),duration=Number(process.argv[4]||100);
if(![0x10,0x20,0x40,0x80,1,2,8].includes(mask)||duration<20||duration>500)throw Error('Invalid bounded menu pulse');
const session=await frida.attach(pid),script=await session.createScript(`
const base=Process.getModuleByName('game.exe').base,until=Date.now()+${duration};let calls=0;const pads={};
if(base.add(0x1548c0).readU8()!==0x55||base.add(0x1548c1).readU16()!==0xec8b)throw Error('Native controller signature mismatch');
Interceptor.attach(base.add(0x1548c0),{onEnter(args){this.pad=args[0].toUInt32();this.out=args[1];},onLeave(){if(Date.now()<until&&this.pad<4){this.out.writeU32(this.out.readU32()|${mask});calls++;pads[this.pad]=(pads[this.pad]||0)+1;}}});
setTimeout(()=>send({calls,pads,mask:${mask},duration:${duration}}),${duration+150});
`);
try{const result=await new Promise(async(resolve,reject)=>{script.message.connect(m=>{if(m.type==='send')resolve(m.payload);else if(m.type==='error')reject(Error(m.stack));});await script.load();});process.stdout.write(JSON.stringify(result)+'\n');}finally{await script.unload();await session.detach();}
