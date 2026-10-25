param([string]$DllPath=(Join-Path $PSScriptRoot '../out/build/d3d9.dll'))
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../debug-v2/toolchain.ps1')
$taskCompiler=Initialize-AriaToolchain
$taskOut=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../out/tests'))
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
Push-Location -LiteralPath $taskOut
try {
    & $taskCompiler /nologo /O2 /MT /W4 /EHsc /Fe:version-guard.exe (Join-Path $PSScriptRoot '../tests/version_guard.cpp') /link /INCREMENTAL:NO
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the x86 version-guard harness.' }
    & (Join-Path $taskOut 'version-guard.exe') ([IO.Path]::GetFullPath($DllPath))
    if ($LASTEXITCODE -ne 0) { throw "Offline version-guard test failed: $LASTEXITCODE" }
} finally { Pop-Location }
