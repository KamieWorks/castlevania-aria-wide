"""Record the reviewed tracked/staged public distribution (excluding itself)."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
files=[]
for name in sorted(filter(None,names)):
    if name=='source-distribution.json':continue
    data=(ROOT/name).read_bytes();files.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
record={'baseline':'v26','shippingCore':'aria-wide/src','scope':'Authored shipping/historical source, development tools, build inputs and documentation; no game or private runtime data.','manifestExcludesItself':True,'files':files}
(ROOT/'source-distribution.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('Recorded',len(files),'public files; stage and rerun publication review before committing.')
