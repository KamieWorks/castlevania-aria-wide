"""Verify the minimal player ZIP and its complete upstream license."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('zip',type=Path);parser.add_argument('--dll',type=Path,required=True);args=parser.parse_args()
with zipfile.ZipFile(args.zip) as archive:
    names=archive.namelist()
    assert len(names)==2 and set(names)=={'d3d9.dll','README.txt'},names
    assert archive.read('d3d9.dll')==args.dll.read_bytes()
    assert (ROOT/'aria-wide/vendor/minhook/LICENSE.txt').read_bytes() in archive.read('README.txt')
print('Two-file package and complete third-party license passed; ZIP SHA256:',hashlib.sha256(args.zip.read_bytes()).hexdigest())
