param([switch]$RealtimeOnly,[string]$DllName='realtime.dll',[switch]$Proxy,[switch]$RendererOnly,[string]$RendererName='render-prototype.dll',[int]$FailStage=0)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'toolchain.ps1')
$taskCompiler=Initialize-AriaToolchain
$taskOut=Get-AriaDebugRoot
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
Push-Location -LiteralPath $taskOut
try {
    if (!$RealtimeOnly) {
        & $taskCompiler /nologo /LD /O2 /MT /W4 /EHsc /Fe:$RendererName /Fo:render-prototype.obj (Join-Path $PSScriptRoot 'render-prototype.cpp') /link /INCREMENTAL:NO
        if ($LASTEXITCODE -ne 0) { throw 'Prototype compilation failed.' }
    }
    if ($RendererOnly) { return }
    $taskMh=Join-Path $PSScriptRoot '../aria-wide/vendor/minhook'
    $taskSource=Join-Path $PSScriptRoot '../aria-wide/src'
    $taskExtra=@()
    if ($FailStage -lt 0 -or $FailStage -gt 3) { throw 'Invalid failure stage.' }
    if ($FailStage) { $taskExtra+="/DARIA_FAIL_STAGE=$FailStage" }
    $taskLink=@('/INCREMENTAL:NO')
    if ($Proxy) { $taskExtra+=Join-Path $taskSource 'proxy.cpp';$taskLink+="/DEF:$taskSource/proxy.def" }
    & $taskCompiler /nologo /LD /O2 /MT /W4 /EHsc "/I$taskMh/include" /Fe:$DllName "$taskSource/realtime.cpp" @taskExtra "$taskMh/src/buffer.c" "$taskMh/src/hook.c" "$taskMh/src/trampoline.c" "$taskMh/src/hde/hde32.c" /link @taskLink
    if ($LASTEXITCODE -ne 0) { throw 'Realtime compilation failed.' }
} finally { Pop-Location }
