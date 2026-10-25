"""Install only a known experimental build when the verified game is absent."""
from debug_config import debug_root
import argparse,pathlib,hashlib,os,shutil,time,subprocess,sys
from harness import identify,ROOT,EXE
parser=argparse.ArgumentParser();parser.add_argument('name');args=parser.parse_args()
try:identify()
except RuntimeError as e:
    if 'found []' not in str(e):raise
else:raise RuntimeError('Close the game before replacing the proxy')
if pathlib.Path(args.name).name!=args.name:raise ValueError('Expected a test DLL basename')
temp=debug_root();source=temp/args.name
if not source.is_file():raise RuntimeError('Test build not found')
destination=EXE.parent/'d3d9.dll'
if destination.exists():
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    if not any(hashlib.sha256(f.read_bytes()).hexdigest()==digest for f in temp.glob('d3d9-v*-test.dll')):raise RuntimeError('Unrecognized active proxy')
    backup=ROOT/'private-v2/test-dll-backups';backup.mkdir(exist_ok=True)
    os.replace(destination,backup/f'd3d9-{digest[:12]}-{time.time_ns()}.dll')
shutil.copy2(source,destination)
print({'deployed':args.name,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
subprocess.run([sys.executable,str(ROOT/'debug-v2/quiet-game.py'),'--launch','--seconds','8'],check=True,timeout=25)
