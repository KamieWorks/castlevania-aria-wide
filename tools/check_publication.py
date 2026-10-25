"""Scan tracked/staged blobs. Report locations and rules, never matched secrets."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'private-key':r'-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY)-----',
    'github-token':r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    'api-token':r'\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,})\b',
    'credential-in-url':r'https?://[^\s/@:]+:[^\s/@]+@',
    'credential-literal':r'''(?i)(?:api[_-]?key|password|passwd|access[_-]?token|client[_-]?secret|authorization|cookie)\s*[:=]\s*["']([^"'\r\n]{5,})''',
    'personal-steam-profile':r'(?i)userdata[/\\]+\d+[/\\]+1552550',
    'personal-home-directory':r'(?i)[A-Z]:[/\\]+Users[/\\]+(?!Developer\b|Public\b|Username\b|<USER>)[^\s"\x27`/\\]+',
}
FORBIDDEN_SUFFIXES={'.exe','.dll','.lib','.exp','.obj','.pdb','.bin','.gba','.psb','.ppu','.ewram','.iwram','.rgb555','.log','.dmp','.sav','.zip','.7z','.png','.jpg','.mp3','.ogg','.mp4','.safetensors','.gguf'}
FORBIDDEN_PARTS={'.git','out','node_modules','.venv','__pycache__','private-v2','tools-v2','diagnostics-v2','game','player','backups','saves','.ssh'}

def blobs(staged):
    entries=subprocess.check_output(['git','ls-files','-s','-z'],cwd=ROOT).decode('utf-8').split('\0')
    for item in filter(None,entries):
        meta,name=item.split('\t',1);mode,oid,stage=meta.split()
        if stage!='0' or mode!='100644':raise RuntimeError('Unreviewed mode or merge stage: '+name)
        data=subprocess.check_output(['git','cat-file','blob',oid],cwd=ROOT) if staged else (ROOT/name).read_bytes()
        yield name,data

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--staged',action='store_true');args=parser.parse_args()
    findings=[];count=total=0
    for name,data in blobs(args.staged):
        count+=1;total+=len(data);path=Path(name)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or set(path.parts)&FORBIDDEN_PARTS or path.name.startswith('.env'):
            findings.append({'file':name,'rule':'excluded-file'})
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:findings.append({'file':name,'rule':'non-text'});continue
        if '\0' in text:findings.append({'file':name,'rule':'binary-content'})
        for number,line in enumerate(text.splitlines(),1):
            for rule,pattern in PATTERNS.items():
                if re.search(pattern,line):findings.append({'file':name,'line':number,'rule':rule})
            for value in re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])',line):
                try:address=ipaddress.ip_address(value)
                except ValueError:continue
                if address.is_private and not address.is_loopback and not address.is_unspecified:findings.append({'file':name,'line':number,'rule':'private-network-address'})
            for value in re.findall(r'(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}',line):
                if not value.endswith('@users.noreply.github.com'):findings.append({'file':name,'line':number,'rule':'unreviewed-email'})
    result={'mode':'staged' if args.staged else 'tracked','files':count,'bytes':total,'findings':findings}
    print(json.dumps(result,indent=2));return bool(findings) or count==0

if __name__=='__main__':raise SystemExit(main())
