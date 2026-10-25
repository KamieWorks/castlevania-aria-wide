import * as frida from 'frida';
import fs from 'node:fs';
import readline from 'node:readline';

const session = await frida.attach(Number(process.argv[2]));
const script = await session.createScript(fs.readFileSync(new URL('./probe.js', import.meta.url), 'utf8'));
script.message.connect(message => { if (message.type === 'error') process.stderr.write(JSON.stringify(message) + '\n'); });
await script.load();
process.stdout.write(JSON.stringify({ready:true})+'\n');
const lines = readline.createInterface({input:process.stdin, crlfDelay:Infinity});
try {
  for await (const line of lines) {
    const request = JSON.parse(line);
    try {
      const result = await script.exports[request.method](...(request.args || []));
      process.stdout.write(JSON.stringify({id:request.id,result})+'\n');
    } catch(e) { process.stdout.write(JSON.stringify({id:request.id,error:String(e)})+'\n'); }
  }
} finally { await script.exports.cleanup(); await script.unload(); await session.detach(); }
