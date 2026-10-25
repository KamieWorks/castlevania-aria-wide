"""Audit installed v23, current user profile, scoped evidence and exact ZIPs."""
from debug_config import profile_root, debug_root
import hashlib,json,os,pathlib,zipfile
import pefile
import numpy as np
from harness import ROOT,EXE,EXPECTED,identify
SHA='2306a11ec0b5577268d6fd7c1435b3f24ec228b2e24df2e2114f96fa682dd1fe'
def digest(data):return hashlib.sha256(data).hexdigest()
def read(name):return json.loads((ROOT/'diagnostics-v2'/name).read_text(encoding='utf-8'))
report={'version':'v23','dllSha256':SHA,'checks':[],'archives':{}}
binary=(ROOT/'aria-wide/build/d3d9.dll').read_bytes()
assert digest(binary)==SHA==digest((EXE.parent/'d3d9.dll').read_bytes())
assert digest(EXE.read_bytes())==EXPECTED
pe=pefile.PE(data=binary);assert pe.FILE_HEADER.Machine==0x14c and pe.FILE_HEADER.Characteristics&0x2000
imports=sorted(x.dll.decode('ascii').lower() for x in pe.DIRECTORY_ENTRY_IMPORT)
assert set(imports)<={'bcrypt.dll','kernel32.dll','user32.dll'},imports
exports={x.name.decode('ascii') for x in pe.DIRECTORY_ENTRY_EXPORT.symbols if x.name}
assert 'Direct3DCreate9' in exports and not any(x.startswith('Debug') for x in exports)
report.update(machine='x86',imports=imports,exeUnchanged=True)
config=(ROOT/'aria-wide/AriaWide.ini').read_bytes()
assert config==(EXE.parent/'AriaWide.ini').read_bytes() and b'ExtendFixedRooms=0' in config
source=(ROOT/'aria-wide/src/realtime.cpp').read_text()
assert 'static bool extendFixedRooms=false;' in source and 'if(bg==1&&mainLayerBackdrop' in source
assert 'L"ExtendFixedRooms",0,configPath' in source
assert 'marginState.version=6;' in source
suite=read('final-v23-45104-check.json');hud=read('hud-v23-25836-check.json');parallax=read('parallax-v23-50968-check.json')
for evidence in [suite,hud,parallax]:
    assert evidence['passed'] and evidence['dllSha256']==SHA and evidence['realSavesUnchanged']
    assert evidence['exit']['exitCode']=='0x0'
assert len(suite['tests'])==8 and all(x['exitCode']==0 for x in suite['tests'])
assert len(suite['fixedRooms'])==2 and all(x['centerEqual'] and x['sidePixels']==0 for x in suite['fixedRooms'])
assert suite['halfSpeedParallax']['equal']==1 and suite['halfSpeedParallax']['backgroundPixels']>50
assert {x['viewport']['left'] for x in hud['samples']}=={0,24,48}
assert all(x['topEqual']==x['rightEqual']==1 and x['topPixels']>500 and x['rightPixels']>50 for x in hud['samples'])
assert hud['actualSkeleton']['nativeInputOnly'] and hud['actualSkeleton']['nameId']==688
assert parallax['freezeVerified'] and parallax['leftFreezeVerified'] and parallax['idleWaterDifferentPixels']>0
assert parallax['stoppedForegroundPair']['equal']==parallax['leftStoppedForegroundPair']['equal']==1
baseline=read('parallax-v22-baseline-33464-check.json');assert baseline['passed'] and baseline['baselineReproduced'] and baseline['stoppedForegroundPair']['differentPixels']>100
tmp=debug_root()
stable=[]
for row in baseline['samples']:
    raw=(tmp/(row['label']+'.ppu')).read_bytes();scroll=int.from_bytes(raw[0x21ffc:0x21ffe],'little')
    if row['wideCamera']==224 and (scroll&511)-row['left']==224:stable.append(row)
a,b=stable[0],stable[-1];assert b['camera']-a['camera']>=6
pa=np.fromfile(tmp/(a['label']+'.rgb555'),dtype='<u2').reshape(162,288)[41:89]&0x7fff
pb=np.fromfile(tmp/(b['label']+'.rgb555'),dtype='<u2').reshape(162,288)[41:89]&0x7fff
report['baselineSameRasterRegion']={'a':a['label'],'b':b['label'],'differentPixels':int(np.sum(pa!=pb)),'nativeCameraDelta':b['camera']-a['camera']}
assert report['baselineSameRasterRegion']['differentPixels']>100
report['checks']=['fixed-rooms-default-off-code-retained','HUD-left-middle-right-and-native-skeleton-hit','parallax-failure-before-success-after-both-edges-and-water-animation','second-room-half-speed-parallax','eight-render-history-menu-regressions']
remote=profile_root()
current={p.name:digest(p.read_bytes()) for p in remote.iterdir() if p.is_file()}
assert current==read('user-regressions-profile-baseline.json')['hashes']
assert all(current==e['before']==e['after'] for e in [suite,hud,parallax])
report['realSavesUnchanged']=True;report['achievementChecks']=[]
for name in ['final-v23-45104','hud-25836','parallax-50968']:
    events=[json.loads(x) for x in (debug_root()/name/'events.jsonl').read_text().splitlines()]
    comparisons=[e for e in events if e.get('type')=='achievement-comparison']
    assert len(comparisons)==1 and comparisons[0]['comparable']==48 and comparisons[0]['changed']==0
    assert not any('error' in e for e in events)
    report['achievementChecks'].append({'run':name,**comparisons[0]})
audio=read('audio-restoration-check.json')
assert audio['pid']==50968 and audio['restoredStoppedGameSessions']==5 and not audio['gameWasRunningDuringUnmute']
assert len(audio['sessions'])==5 and all(x['before'] is True and x['after'] is False for x in audio['sessions'])
quiet=read('quiet-game-check.json');assert quiet['pid']==50968 and quiet['backgroundGuard'] and not quiet['gameForegroundObserved']
assert len(quiet['audioSessions'])==5 and all(x['muted'] for x in quiet['audioSessions'])
report['checks']+=['real-profile-and-48-achievements-unchanged','muted-hidden-debug-and-five-audio-endpoints-restored-after-exit']
try:identify()
except RuntimeError as e:assert 'found []' in str(e),str(e)
else:raise AssertionError('Diagnostic game remains running')
report['noGameRunning']=True
vendor=ROOT/'aria-wide/vendor/minhook';third=json.loads((vendor/'source-manifest.json').read_text())
assert third['commit']=='8af6b4acae5a9388fd742b56fa79ece89d96f823'
for name,sha in third['files'].items():assert digest((vendor/name).read_bytes())==sha,name
report['thirdPartyFilesVerified']=len(third['files'])
for kind,filename in [('player','AriaWide-v23.zip'),('source','AriaWide-v23-source.zip')]:
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
checkpoint=ROOT/'private-v2/checkpoints/v23-final'
assert digest((checkpoint/'d3d9.dll').read_bytes())==SHA
for name in ['realtime.cpp','proxy.cpp','proxy.def']:assert (checkpoint/'src'/name).read_bytes()==(ROOT/'aria-wide/src'/name).read_bytes()
for folder in ['v20-before-user-regressions','v21-fixed-default-off','v22-hud-anchored']:assert (ROOT/'private-v2/checkpoints'/folder/'d3d9.dll').is_file()
report['checks'].append('archives-member-hashes-source-identity-licenses-and-rollback-checkpoints')
report['passed']=True
(ROOT/'diagnostics-v2/release-v23-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)

