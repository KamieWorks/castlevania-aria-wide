"""Audit v25 corner layouts, continuous edge frames, release ZIPs and profile."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,zipfile
import numpy as np
import pefile
from harness import ROOT,EXE,EXPECTED,identify
SHA='923a6bc5938fb3c08f2762bf65333859d39bab0759616157fe57da67c0fc540c'
def digest(data):return hashlib.sha256(data).hexdigest()
def read(name):return json.loads((ROOT/'diagnostics-v2'/name).read_text(encoding='utf-8'))
report={'version':'v25','dllSha256':SHA,'checks':[],'archives':{}}
binary=(ROOT/'aria-wide/build/d3d9.dll').read_bytes()
assert digest(binary)==SHA==digest((EXE.parent/'d3d9.dll').read_bytes())
assert digest(EXE.read_bytes())==EXPECTED
pe=pefile.PE(data=binary);assert pe.FILE_HEADER.Machine==0x14c and pe.FILE_HEADER.Characteristics&0x2000
imports=sorted(x.dll.decode('ascii').lower() for x in pe.DIRECTORY_ENTRY_IMPORT)
assert set(imports)<={'bcrypt.dll','kernel32.dll','user32.dll'},imports
exports={x.name.decode('ascii') for x in pe.DIRECTORY_ENTRY_EXPORT.symbols if x.name}
assert 'Direct3DCreate9' in exports and 'GetBackgroundCorrections' in exports and not any(x.startswith('Debug') for x in exports)
report.update(machine='x86',imports=imports,exeUnchanged=True)
config=(ROOT/'aria-wide/AriaWide.ini').read_bytes()
assert config==(EXE.parent/'AriaWide.ini').read_bytes() and b'ExtendFixedRooms=0' in config
source=(ROOT/'aria-wide/src/realtime.cpp').read_text(encoding='utf-8')
assert 'static bool extendFixedRooms=false;' in source and 'if(bg==1&&mainLayerBackdrop' in source
assert 'L"ExtendFixedRooms",0,configPath' in source and 'marginState.version=8;' in source
suite=read('final-v25-47660-check.json');hud=read('hud-corners-v25-11340-check.json');jitter=read('jitter-v25-51616-check.json')
for evidence in [suite,hud,jitter]:
    assert evidence['passed'] and evidence['dllSha256']==SHA and evidence['realSavesUnchanged']
    assert evidence['exit']['exitCode']=='0x0'
assert len(suite['tests'])==8 and all(x['exitCode']==0 for x in suite['tests'])
assert len(suite['fixedRooms'])==2 and all(x['centerEqual'] and x['sidePixels']==0 for x in suite['fixedRooms'])
assert suite['halfSpeedParallax']['equal']==1 and suite['halfSpeedParallax']['backgroundPixels']>50
assert len(hud['samples'])==12 and {x['viewport']['left'] for x in hud['samples']}=={0,24,48}
assert {x['kind'] for x in hud['samples']}=={'enemy','item','soul','soul-modal'}
assert all(x['topEqual']==x['noticeEqual']==1 and x['topPixels']>500 and x['noticePixels']>50 for x in hud['samples'])
report['naturalPickupOrSoulAwardTested']=False
baseline=read('jitter-v24-44800-check.json');assert baseline['passed'] and all(c['phaseErrorFrames'] for c in baseline['cases'])
assert len(jitter['cases'])==4
report['denseFrames']=0;report['denseCases']=[]
for case in jitter['cases']:
    rows=case['telemetry'];assert len(rows)==96 and not case['phaseErrorFrames']
    for r in rows:
        expected=max(0,min(224,r['rasterCamera']-24))
        assert r['rasterWideCamera']==r['rasterCamera']-r['viewport']['left']==expected
    limit=224 if case['direction']=='right' else 0
    clamped=[i for i,r in enumerate(rows) if r['expectedWide']==limit]
    assert len(clamped)>15 and max(rows[i]['rasterCamera'] for i in clamped)-min(rows[i]['rasterCamera'] for i in clamped)>=16
    bg=3 if case['fixture']=='slot1-hud-info' else 2
    origins={(rows[i]['scroll'][bg]+rows[i]['corrections'][bg]-rows[i]['viewport']['left'])&511 for i in clamped}
    assert len(origins)==1
    prefix=pathlib.Path(case['framePrefix']);pixels=np.fromfile(str(prefix)+'.frames.rgb555',dtype='<u2').reshape(96,162,288)[:,1:161]&0x7fff
    if case['fixture']=='slot1-hud-info':
        assert all(np.array_equal(pixels[a,40:88],pixels[b,40:88]) for a,b in zip(clamped,clamped[1:]) if b==a+1)
        water=sum(int(np.sum(pixels[a,140:160]!=pixels[b,140:160])) for a,b in zip(clamped,clamped[1:]))
        assert water>0
    else:water=None
    directory=ROOT/f'diagnostics-v2/dense-{jitter["pid"]}-{case["fixture"]}-{case["direction"]}'
    assert len(list(directory.glob('*.png')))==96
    report['denseFrames']+=96
    report['denseCases'].append({'fixture':case['fixture'],'direction':case['direction'],'phaseErrors':0,'backgroundOrigins':sorted(origins),'waterChangingPixels':water,'distinctPixelFrames':len({digest(x.tobytes()) for x in pixels})})
report['checks']=['twelve-corner-and-modal-layouts','384-consecutive-moving-edge-frames-before-after','latched-camera-and-fractional-parallax-phase','water-animation-retained','eight-render-history-menu-regressions','fixed-rooms-default-off-code-retained']
remote=profile_root()
current={p.name:digest(p.read_bytes()) for p in remote.iterdir() if p.is_file()}
assert current==read('hud-v24-profile-baseline.json')['hashes']
assert all(current==e['before']==e['after'] for e in [suite,hud,jitter])
report['realSavesUnchanged']=True;report['achievementChecks']=[]
for name in ['final-v25-47660','hud-11340','jitter-51616']:
    events=[json.loads(x) for x in (debug_root()/name/'events.jsonl').read_text().splitlines()]
    comparisons=[e for e in events if e.get('type')=='achievement-comparison']
    assert len(comparisons)==1 and comparisons[0]['comparable']==48 and comparisons[0]['changed']==0
    assert not any('error' in e for e in events)
    report['achievementChecks'].append({'run':name,**comparisons[0]})
audio=read('audio-restoration-check.json')
assert audio['pid']==47660 and audio['restoredStoppedGameSessions']==5 and not audio['gameWasRunningDuringUnmute']
assert len(audio['sessions'])==5 and all(x['before'] is True and x['after'] is False for x in audio['sessions'])
quiet=read('quiet-game-check.json');assert quiet['pid']==47660 and quiet['backgroundGuard'] and not quiet['gameForegroundObserved']
assert len(quiet['audioSessions'])==5 and all(x['muted'] for x in quiet['audioSessions'])
report['checks']+=['current-profile-and-48-achievements-unchanged','hidden-muted-debug-and-audio-restored-after-exit']
try:identify()
except RuntimeError as e:assert 'found []' in str(e),str(e)
else:raise AssertionError('Diagnostic game remains running')
report['noGameRunning']=True
vendor=ROOT/'aria-wide/vendor/minhook';third=json.loads((vendor/'source-manifest.json').read_text())
assert third['commit']=='8af6b4acae5a9388fd742b56fa79ece89d96f823'
for name,sha in third['files'].items():assert digest((vendor/name).read_bytes())==sha,name
report['thirdPartyFilesVerified']=len(third['files'])
for kind,filename in [('player','AriaWide-v25.zip'),('source','AriaWide-v25-source.zip')]:
    path=ROOT/'deliverables'/filename
    with zipfile.ZipFile(path) as z:
        files=[x.filename for x in z.infolist() if not x.is_dir()]
        assert len(files)==len(set(files)) and all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in files)
        sums={x.split('  ',1)[1]:x.split('  ',1)[0] for x in z.read('SHA256SUMS.txt').decode('utf-8-sig').splitlines()}
        assert set(sums)==set(files)-{'SHA256SUMS.txt'}
        for name,sha in sums.items():assert digest(z.read(name))==sha,(filename,name)
        if kind=='player':
            assert set(files)=={'d3d9.dll','AriaWide.ini','README.zh-CN.md','VALIDATION.zh-CN.md','THIRD-PARTY.md','LICENSE-MinHook.txt','SHA256SUMS.txt'}
            assert digest(z.read('d3d9.dll'))==SHA and z.read('AriaWide.ini')==config
            assert z.read('LICENSE-MinHook.txt')==(vendor/'LICENSE.txt').read_bytes()
        else:
            allowed={'AriaWide.ini','README.zh-CN.md','VALIDATION.zh-CN.md','THIRD-PARTY.md','build.ps1','package.ps1'}
            for name in sums:
                assert name in allowed or name.startswith('src/') or name.startswith('vendor/'),name
                assert z.read(name)==(ROOT/'aria-wide'/name).read_bytes(),name
        report['archives'][kind]={'path':str(path),'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size,'verifiedFiles':len(files)}
checkpoint=ROOT/'private-v2/checkpoints/v25-final'
assert digest((checkpoint/'d3d9.dll').read_bytes())==SHA
for name in ['realtime.cpp','proxy.cpp','proxy.def']:assert (checkpoint/'src'/name).read_bytes()==(ROOT/'aria-wide/src'/name).read_bytes()
for folder in ['v20-before-user-regressions','v21-fixed-default-off','v22-hud-anchored','v23-final','v24-hud-corners']:assert (ROOT/'private-v2/checkpoints'/folder/'d3d9.dll').is_file()
report['checks'].append('archives-member-hashes-source-identity-licenses-and-rollback-checkpoints')
report['passed']=True
(ROOT/'diagnostics-v2/release-v25-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)

