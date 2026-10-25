"""Verify the actual release archives, installed files and scoped evidence."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,zipfile
import pefile
from harness import ROOT,EXE,EXPECTED,identify

SHA='77063154a0e1a77869e4e424bed6fc07423d9934af9e4677ed6ae630ee8d30c0'
def digest(data):return hashlib.sha256(data).hexdigest()
def read(name):return json.loads((ROOT/'diagnostics-v2'/name).read_text(encoding='utf-8'))
report={'version':'v20','dllSha256':SHA,'checks':[],'archives':{}}
binary=(ROOT/'aria-wide/build/d3d9.dll').read_bytes()
assert digest(binary)==SHA==digest((EXE.parent/'d3d9.dll').read_bytes())
assert digest(EXE.read_bytes())==EXPECTED
pe=pefile.PE(data=binary);assert pe.FILE_HEADER.Machine==0x14c and pe.FILE_HEADER.Characteristics&0x2000
imports=sorted(x.dll.decode('ascii').lower() for x in pe.DIRECTORY_ENTRY_IMPORT)
assert set(imports)<= {'bcrypt.dll','user32.dll','kernel32.dll'},imports
exports=[x.name.decode('ascii') for x in pe.DIRECTORY_ENTRY_EXPORT.symbols if x.name]
assert 'Direct3DCreate9' in exports
report.update(machine='x86',imports=imports,exeUnchanged=True)
for name in ['AriaWide.ini']:
    assert (EXE.parent/name).read_bytes()==(ROOT/'aria-wide'/name).read_bytes()
manifest=read('live-suite-v20-49368-check.json')
assert manifest['passed'] and len(manifest['tests'])==9 and manifest['dllSha256']==SHA
rooms=read('bossrush-rooms-30900-check.json')
assert rooms['passed'] and rooms['dllSha256']==SHA and len(rooms['rooms'])==24
assert all(r['passed'] and len(r['samples'])==3 and all(s['centerEqual'] for s in r['samples']) for r in rooms['rooms'])
report['checks']+=['v20-nine-regressions','v20-24-extra-scenes-72-captures']
for code in ['A2CE','A2CP']:
    region=read(f'region-runtime-{code}-check.json')
    assert region['passed'] and abs(region['movement']['worldXDelta'])>10
    assert all(s['centerEqual'] for s in region['samples'])
report['checks'].append('native-US-EU-menu-room-movement')
reset=read('device-reset-28736-check.json')
assert reset['passed'] and reset['dllSha256']==SHA and reset['exit']['exitCode']=='0x0'
assert reset['native']['resetReturned'] and reset['native']['afterFrames']>=60
assert reset['afterFrame']['romCode']=='A2CJ' and reset['centerEqual']
console=read('console-32380-check.json');assert console['realSavesUnchanged'] and console['exit']['exitCode']=='0x0'
codes=[c['result'] for c in console['commands'] if c.get('rpc')=='romcode' and 'result' in c]
assert codes[-1]=='A2CJ'
audio=read('audio-restoration-check.json')
assert audio['pid']==28736 and audio['restoredStoppedGameSessions']==5 and not audio['gameWasRunningDuringUnmute']
assert len(audio['sessions'])==5 and all(s['after'] is False for s in audio['sessions'])
report['checks']+=['v20-native-device-reset-and-exit','JP-restored','five-audio-endpoints-restored-after-exit']
remote=profile_root()
current={p.name:digest(p.read_bytes()) for p in remote.iterdir() if p.is_file()}
assert current==reset['before']==reset['after']==console['before']==console['after']
report['realSavesUnchanged']=True
report['achievementChecks']=[]
for name in ['live-suite-49368','bossrush-rooms-30900','console-32380','reset-28736']:
    events=[json.loads(line) for line in (debug_root()/name/'events.jsonl').read_text().splitlines()]
    comparisons=[e for e in events if e.get('type')=='achievement-comparison']
    assert len(comparisons)==1 and comparisons[0]['comparable']==48 and comparisons[0]['changed']==0
    assert not any('error' in e for e in events)
    report['achievementChecks'].append({'run':name,**comparisons[0]})
try:identify()
except RuntimeError as e:assert 'found []' in str(e),str(e)
else:raise AssertionError('Diagnostic game still running')
report['noGameRunning']=True
vendor=ROOT/'aria-wide/vendor/minhook';third=json.loads((vendor/'source-manifest.json').read_text())
assert third['commit']=='8af6b4acae5a9388fd742b56fa79ece89d96f823'
for name,sha in third['files'].items():assert digest((vendor/name).read_bytes())==sha,name
report['thirdPartyFilesVerified']=len(third['files'])
for kind,filename in [('player','AriaWide-v20.zip'),('source','AriaWide-v20-source.zip')]:
    path=ROOT/'deliverables'/filename
    with zipfile.ZipFile(path) as z:
        files=[i.filename for i in z.infolist() if not i.is_dir()]
        assert len(files)==len(set(files)) and all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in files)
        sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in z.read('SHA256SUMS.txt').decode('utf-8-sig').splitlines()}
        assert set(sums)==set(files)-{'SHA256SUMS.txt'}
        for name,sha in sums.items():assert digest(z.read(name))==sha,(filename,name)
        if kind=='player':
            assert set(files)=={'d3d9.dll','AriaWide.ini','README.zh-CN.md','VALIDATION.zh-CN.md','THIRD-PARTY.md','LICENSE-MinHook.txt','SHA256SUMS.txt'}
            assert digest(z.read('d3d9.dll'))==SHA
            assert z.read('LICENSE-MinHook.txt')==(vendor/'LICENSE.txt').read_bytes()
        else:
            allowed={'AriaWide.ini','README.zh-CN.md','VALIDATION.zh-CN.md','THIRD-PARTY.md','build.ps1','package.ps1'}
            for name in sums:
                assert name in allowed or name.startswith('src/') or name.startswith('vendor/'),name
                assert z.read(name)==(ROOT/'aria-wide'/name).read_bytes(),name
        report['archives'][kind]={'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes()),'verifiedFiles':len(files)}
report['passed']=True
(ROOT/'diagnostics-v2/release-v20-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
