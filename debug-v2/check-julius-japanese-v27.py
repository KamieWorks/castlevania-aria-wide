"""Temporarily remove only hash-verified translation overlays for a JP cold run."""
import hashlib,json,pathlib,shutil,subprocess,sys
from harness import EXE,ROOT,identify
work=pathlib.Path(sys.argv[1]).resolve();assert work.is_dir()
try:identify()
except RuntimeError as e:assert 'found []' in str(e)
else:raise RuntimeError('A game process is already running')
expected={'patchdata.bin':'d122ea3e203e9404dee0f03d3d84612b9b250f57068a90336c7bedf5d668fadb','patchdata.psb.m':'71506afd00334662aef6818ac56dbafbd6619364556003e5c7d24432220283d2'}
backup=ROOT/'private-v2/checkpoints/v27-before/translation';backup.mkdir(exist_ok=True)
removed=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
try:
 for name,want in expected.items():
  p=EXE.parent/'windata'/name;assert sha(p)==want
  dest=backup/name
  if dest.exists():assert sha(dest)==want
  else:shutil.copy2(p,dest)
  assert sha(dest)==want;p.unlink();removed.append(name)
 subprocess.run([sys.executable,str(ROOT/'debug-v2/quiet-game.py'),'--launch','--seconds','8'],check=True,timeout=40)
 subprocess.run([sys.executable,str(ROOT/'debug-v2/check-julius-hud-v27.py'),'--scratch',str(work),'--variant','japanese'],check=True,timeout=220)
finally:
 try:identify()
 except RuntimeError as e:assert 'found []' in str(e)
 else:subprocess.run([sys.executable,str(ROOT/'debug-v2/restore-audio-after-close.py')],check=True,timeout=40)
 for name in removed:
  dest=EXE.parent/'windata'/name;assert not dest.exists();shutil.copy2(backup/name,dest);assert sha(dest)==expected[name]
 (ROOT/'diagnostics-v2/julius-v27/translation-restored.json').write_text(json.dumps({'files':expected,'restored':True},indent=2))
