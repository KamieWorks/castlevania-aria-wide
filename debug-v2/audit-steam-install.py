"""Read the installed Steam depot manifest and reversibly quarantine extras."""
from debug_config import profile_root, depot_manifest
import argparse,datetime,hashlib,json,pathlib,shutil,struct,sys
from harness import ROOT,EXE,identify
MANIFEST=depot_manifest()
REMOTE=profile_root()
def digest(p,algorithm='sha256'):
 with p.open('rb') as f:return hashlib.file_digest(f,algorithm).hexdigest()
def fields(data):
 pos=0
 def number():
  nonlocal pos
  n=s=0
  while True:
   if pos>=len(data):raise ValueError('Truncated depot protobuf')
   v=data[pos];pos+=1;n|=(v&127)<<s
   if not v&128:return n
   s+=7
   if s>=70:raise ValueError('Oversized protobuf integer')
 while pos<len(data):
  tag=number();f,w=tag>>3,tag&7
  if w==0:value=number()
  elif w==2:
   size=number();value=data[pos:pos+size];pos+=size
   if len(value)!=size:raise ValueError('Truncated bytes')
  elif w in [1,5]:size=8 if w==1 else 4;value=data[pos:pos+size];pos+=size
  else:raise ValueError('Unknown protobuf field')
  yield f,value

def expected_files():
 b=MANIFEST.read_bytes();magic,size=struct.unpack_from('<II',b);assert magic==0x71f617d0 and 8+size<len(b)
 result={}
 for tag,data in fields(b[8:8+size]):
  assert tag==1;d=dict(fields(data));name=d[1].decode().replace('\\','/');path=pathlib.PurePosixPath(name)
  assert not path.is_absolute() and '..' not in path.parts and ':' not in name
  if d.get(3,0)&64:continue
  assert name not in result and len(d[5])==20
  result[name]={'bytes':d[2],'sha1':d[5].hex()}
 assert len(result)==93
 return result

def no_game():
 try:identify()
 except RuntimeError as e:
  if 'found []' not in str(e):raise
 else:raise RuntimeError('Close the game before changing installation files')

def audit():
 root=EXE.parent.resolve();expected=expected_files();bad=[];extras=[]
 for name,r in expected.items():
  p=root/name
  if not p.is_file() or p.stat().st_size!=r['bytes'] or digest(p,'sha1')!=r['sha1']:bad.append(name)
 for p in root.rglob('*'):
  assert not p.is_symlink() and p.resolve().is_relative_to(root)
  if p.is_file() and p.relative_to(root).as_posix() not in expected:extras.append(p.relative_to(root).as_posix())
 return {'depot':1552551,'manifest':8609910394922333285,'officialFiles':len(expected),'badOfficialFiles':bad,'extraFiles':extras,'manifestSHA256':digest(MANIFEST)}

def backup_clean():
 no_game();before=audit();assert not before['badOfficialFiles']
 backup=ROOT/'private-v2/install-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
 backup.mkdir(parents=True);shutil.copy2(MANIFEST,backup/MANIFEST.name)
 records=[]
 for name in before['extraFiles']:
  source=EXE.parent/name;destination=backup/'extras'/name;destination.parent.mkdir(parents=True,exist_ok=True)
  sha=digest(source);shutil.copy2(source,destination);assert digest(destination)==sha
  records.append({'path':name,'bytes':source.stat().st_size,'sha256':sha})
 shutil.copytree(REMOTE,backup/'current-profile')
 for p in REMOTE.iterdir():
  if p.is_file():assert digest(p)==digest(backup/'current-profile'/p.name)
 report={'backup':str(backup),'before':before,'files':records,'currentProfile':{p.name:digest(p) for p in REMOTE.iterdir() if p.is_file()}}
 (backup/'manifest.json').write_text(json.dumps(report,indent=2));no_game()
 for r in records:
  p=EXE.parent/r['path'];assert p.resolve().is_relative_to(EXE.parent.resolve()) and digest(p)==r['sha256'];p.unlink()
 for p in sorted((p for p in EXE.parent.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
  assert p.resolve().is_relative_to(EXE.parent.resolve()) and not p.is_symlink()
  if not any(p.iterdir()):p.rmdir()
 after=audit();assert not after['extraFiles'] and not after['badOfficialFiles'];report['after']=after;report['passed']=True
 (ROOT/'diagnostics-v2/steam-clean-restore-check.json').write_text(json.dumps(report,indent=2));print(json.dumps({'backup':str(backup),'backedUpFiles':len(records),'bytes':sum(r['bytes'] for r in records),'officialFiles':after['officialFiles'],'pureSteam':True}))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--backup-clean',action='store_true');args=ap.parse_args()
 if args.backup_clean:backup_clean()
 else:print(json.dumps(audit()))
