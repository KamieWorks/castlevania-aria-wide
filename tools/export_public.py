"""Export reviewed authored source, never a working repository or game data."""
import argparse,ast,hashlib,json,pathlib,re,shutil
TEXT={'.py','.mjs','.js','.cpp','.c','.h','.hpp','.def','.ps1','.cmd','.md','.txt','.json','.ini'}
def sha(data):return hashlib.sha256(data).hexdigest()
def portable(name,data):
 text=data.decode('utf-8-sig');before=text
 if name.endswith('.py'):
  text=re.sub(r"(?i)(remote)\s*=\s*pathlib.Path\(r?'[^']*[\\/]userdata[\\/]\d+[\\/]1552550[\\/]remote'\)",r'\1=profile_root()',text)
  if name=='debug-v2/harness.py':text=re.sub(r"EXE=pathlib.Path\(r?'[^']*game\.exe'\)",'EXE=game_exe()',text)
  if name=='debug-v2/audit-steam-install.py':text=re.sub(r"MANIFEST=pathlib.Path\(r?'[^']*\.manifest'\)",'MANIFEST=depot_manifest()',text)
  text=text.replace("pathlib.Path(os.environ['LOCALAPPDATA'])/'Temp/cva16x9'",'debug_root()')
  text=text.replace("pathlib.Path(os.environ['LOCALAPPDATA'])/'Temp'/'cva16x9'",'debug_root()')
  text=text.replace("scratch.parent==pathlib.Path('D:/CodexScratch')",'not scratch.is_symlink()')
  text=text.replace("assert work.parent.parent==pathlib.Path('D:/CodexScratch')",'assert pathlib.Path(args.scratch).resolve().is_dir()')
  text=re.sub(r"pathlib.Path\(r?'[^']*WindowsApps[^']*cdb\.exe'\)",'debugger_exe()',text)
  functions=[x for x in ['profile_root','debug_root','game_exe','depot_manifest','debugger_exe'] if re.search(r'\b'+x+r'\(',text)]
  if functions:
   tree=ast.parse(text);line=0
   for node in tree.body:
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str) and line==0:line=node.end_lineno
    elif isinstance(node,ast.ImportFrom) and node.module=='__future__':line=node.end_lineno
    else:break
   lines=text.splitlines(keepends=True);lines.insert(line,'from debug_config import '+', '.join(functions)+'\n');text=''.join(lines)
 if name.endswith('.mjs'):
  text=re.sub(r"import \* as frida from '[^']*/frida(?:/build/src/frida\.js)?';","import * as frida from 'frida';",text)
  if name.endswith('allocation-trace.mjs'):
   text=re.sub(r"const exe='[^']*game\.exe';",'const exe=gameExe;',text);text="import {gameExe} from './debug-paths.mjs';\n"+text
  if name.endswith('device-reset-once.mjs'):
   text=re.sub(r"if\(game\.path\.toLowerCase\(\)!==.*?throw Error\('Unexpected process path'\);", "if(game.path.toLowerCase()!==${JSON.stringify(gameExe.toLowerCase())})throw Error('Unexpected process path');",text)
   text="import {gameExe} from './debug-paths.mjs';\n"+text
  if 'Temp/cva16x9' in text:
   text=text.replace("process.env.LOCALAPPDATA.replaceAll('\\\\','/')+'/Temp/cva16x9'","debugRoot.replaceAll('\\\\','/')")
   text=text.replace("process.env.LOCALAPPDATA.replaceAll('\\\\','/')+'/Temp/cva16x9/", "debugRoot.replaceAll('\\\\','/')+'/")
   text="import {debugRoot} from './debug-paths.mjs';\n"+text
 return (text.encode('utf-8') if text!=before else data),text!=before

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=pathlib.Path,required=True);ap.add_argument('--destination',type=pathlib.Path,required=True);args=ap.parse_args()
 root=args.source_root.resolve();dest=args.destination.resolve();assert not dest.exists() and (root/'aria-wide/src/realtime.cpp').is_file();dest.mkdir(parents=True)
 records=[];seen=set()
 def copy(source,target,transform=False):
  assert target not in seen;seen.add(target);raw=source.read_bytes();data,changed=portable(target,raw) if transform else (raw,False)
  out=dest/target;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
  origin=source.relative_to(root).as_posix();origin=origin.removeprefix('private-v2/')
  records.append({'path':target,'origin':origin,'sourceSHA256':sha(raw),'exportSHA256':sha(data),'bytes':len(data),'portableAdaptation':changed})
 for source in (root/'aria-wide').rglob('*'):
  if source.is_file() and 'build' not in source.relative_to(root/'aria-wide').parts and source.suffix in TEXT:copy(source,source.relative_to(root).as_posix())
 for source in (root/'debug-v2').glob('*'):
  if source.is_file() and source.suffix in TEXT:copy(source,source.relative_to(root).as_posix(),True)
 for folder in ['sotn16x9','sotn16x9-release','patch-checkpoints']:
  for source in (root/folder).rglob('*'):
   if source.is_file() and source.suffix in TEXT:copy(source,'historical/'+source.relative_to(root).as_posix(),True)
 for folder in (root/'private-v2/checkpoints').iterdir():
  for source in folder.rglob('*'):
   if source.is_file() and source.suffix in {'.cpp','.def','.ps1'}:
    relative=source.relative_to(folder).as_posix().removeprefix('src/');copy(source,'historical/checkpoints/'+folder.name+'/'+relative,True)
 tool=pathlib.Path(__file__).resolve();out=dest/'tools/export_public.py';out.parent.mkdir(exist_ok=True);shutil.copy2(tool,out)
 (dest/'source-index.json').write_text(json.dumps({'release':'v26','shippingDLLSHA256':'60f4f368cd8fc80480d963cdfb358d59db8b20574e3b78a8036195320ae5dd59','shippingSource':'aria-wide/src','files':records,'excluded':['game executables and ROM/resources','save data and user configuration','private captures and memory dumps','working Git history and machine configuration','generated binaries and downloaded tool distributions']},indent=2),encoding='utf-8')
 print(json.dumps({'destination':str(dest),'sourceFiles':len(records),'adaptedFiles':sum(r['portableAdaptation'] for r in records),'bytes':sum(r['bytes'] for r in records)}))
if __name__=='__main__':main()
