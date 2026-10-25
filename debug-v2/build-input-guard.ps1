$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'toolchain.ps1')
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskCompiler=Initialize-AriaToolchain
$taskDebugRoot=Get-AriaDebugRoot
$taskOut=Join-Path $taskDebugRoot 'input-guard-build'
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
Push-Location -LiteralPath $taskOut
try {
    $taskSources=@('debug-v2/input-guard.cpp','aria-wide/vendor/minhook/src/buffer.c','aria-wide/vendor/minhook/src/hook.c','aria-wide/vendor/minhook/src/trampoline.c','aria-wide/vendor/minhook/src/hde/hde32.c') | ForEach-Object { Join-Path $taskRoot $_ }
    & $taskCompiler /nologo /LD /O2 /MT /W4 /EHsc "/I$taskRoot/aria-wide/vendor/minhook/include" /Fe:debug-input-v1.dll @taskSources /link /INCREMENTAL:NO /DYNAMICBASE /NXCOMPAT
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $LASTEXITCODE" }
    Copy-Item -LiteralPath (Join-Path $taskOut 'debug-input-v1.dll') -Destination (Join-Path $taskDebugRoot 'debug-input-v1.dll')
} finally { Pop-Location }
Get-FileHash -LiteralPath (Join-Path $taskOut 'debug-input-v1.dll') -Algorithm SHA256
