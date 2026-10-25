"""Portable source audit, x86 build, offline guard test and minimal packaging."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    index=json.loads((ROOT/'source-index.json').read_text(encoding='utf-8'))
    for item in index['files']:
        if digest(ROOT/item['path'])!=item['exportSHA256']:
            raise RuntimeError('Source-index mismatch: '+item['path'])
    vendor=ROOT/'aria-wide/vendor/minhook'
    manifest=json.loads((vendor/'source-manifest.json').read_text())
    for name,sha in manifest['files'].items():
        if digest(vendor/name)!=sha:raise RuntimeError('Vendor source mismatch: '+name)
    distribution=ROOT/'source-distribution.json'
    if distribution.is_file():
        for item in json.loads(distribution.read_text(encoding='utf-8'))['files']:
            if digest(ROOT/item['path'])!=item['sha256']:
                raise RuntimeError('Public-distribution mismatch: '+item['path'])
    count=0
    for folder in ['debug-v2','tools']:
        for path in (ROOT/folder).rglob('*.py'):
            ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path));count+=1
    print(json.dumps({'sourceFiles':len(index['files']),'vendorFiles':len(manifest['files']),'pythonFilesParsed':count,'passed':True}))

def powershell(script,*args):
    executable=shutil.which('powershell.exe') or shutil.which('pwsh')
    if not executable:raise RuntimeError('Windows PowerShell and MSVC x86 tools are required.')
    subprocess.run([executable,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/script),*map(str,args)],cwd=ROOT,check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['audit','build','test','package','build-debug'])
    parser.add_argument('--name',default='AriaWide-v26-release')
    args=parser.parse_args()
    if args.action=='audit':audit()
    elif args.action=='build':powershell('aria-wide/build.ps1','-OutputDirectory',ROOT/'out/build')
    elif args.action=='test':powershell('tools/build-smoke.ps1','-DllPath',ROOT/'out/build/d3d9.dll')
    elif args.action=='build-debug':
        powershell('debug-v2/build-input-guard.ps1')
        powershell('debug-v2/build-prototype.ps1','-RendererOnly','-RendererName','render-objects.dll')
    elif args.action=='package':powershell('aria-wide/package.ps1','-PackageName',args.name,'-DllPath',ROOT/'out/build/d3d9.dll','-OutputDirectory',ROOT/'out/releases')

if __name__=='__main__':main()
