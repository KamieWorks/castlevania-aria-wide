param([switch]$RealtimeOnly,[string]$DllName='realtime.dll',[switch]$Proxy,[switch]$RendererOnly,[string]$RendererName='render-prototype.dll',[int]$FailStage=0)
$ErrorActionPreference = 'Stop'
$taskVc = 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231'
$taskSdk = 'C:\Program Files (x86)\Windows Kits\10'
$taskVer = '10.0.26100.0'
$env:PATH = "$taskVc\bin\Hostx64\x86;" + $env:PATH
$env:INCLUDE = "$taskVc\include;$taskSdk\Include\$taskVer\ucrt;$taskSdk\Include\$taskVer\shared;$taskSdk\Include\$taskVer\um"
$env:LIB = "$taskVc\lib\x86;$taskSdk\Lib\$taskVer\ucrt\x86;$taskSdk\Lib\$taskVer\um\x86"
$taskOut = Join-Path $env:LOCALAPPDATA 'Temp\cva16x9'
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
if (!$RealtimeOnly) {
    & "$taskVc\bin\Hostx64\x86\cl.exe" /nologo /LD /O2 /MT /W4 /EHsc /Fe:"$taskOut\$RendererName" /Fo:"$taskOut\render-prototype.obj" "$PSScriptRoot\render-prototype.cpp" /link /INCREMENTAL:NO
    if ($LASTEXITCODE -ne 0) { throw 'Prototype compilation failed' }
}
if($RendererOnly){return}
$taskMh = Join-Path $PSScriptRoot '..\tools-v2\minhook'
Push-Location -LiteralPath $taskOut
try {
    $taskExtra = @()
    if($FailStage -lt 0 -or $FailStage -gt 3){throw 'Invalid failure stage'}
    if($FailStage){$taskExtra+="/DARIA_FAIL_STAGE=$FailStage"}
    $taskLink = @('/INCREMENTAL:NO')
    if($Proxy){$taskExtra+= "$PSScriptRoot\proxy.cpp";$taskLink+="/DEF:$PSScriptRoot\proxy.def"}
    & "$taskVc\bin\Hostx64\x86\cl.exe" /nologo /LD /O2 /MT /W4 /EHsc /I"$taskMh\include" /Fe:"$taskOut\$DllName" "$PSScriptRoot\realtime.cpp" @taskExtra "$taskMh\src\buffer.c" "$taskMh\src\hook.c" "$taskMh\src\trampoline.c" "$taskMh\src\hde\hde32.c" /link @taskLink
    if ($LASTEXITCODE -ne 0) { throw 'Realtime compilation failed' }
} finally { Pop-Location }
