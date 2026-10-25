param([string]$OutputDirectory = "$PSScriptRoot\build")
$ErrorActionPreference = 'Stop'
$taskVswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (!(Test-Path -LiteralPath $taskVswhere)) { throw 'Install Visual Studio C++ build tools with the x86 toolchain and a Windows SDK.' }
$taskVsRoot = (& $taskVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if (!$taskVsRoot) { throw 'No Visual Studio C++ x86 toolchain found.' }
$taskVcVersion = (Get-Content -LiteralPath "$taskVsRoot\VC\Auxiliary\Build\Microsoft.VCToolsVersion.default.txt" -Raw).Trim()
$taskVc = "$taskVsRoot\VC\Tools\MSVC\$taskVcVersion"
$taskSdk = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' -ErrorAction SilentlyContinue).KitsRoot10
if (!$taskSdk) { $taskSdk = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots').KitsRoot10 }
$taskSdkVersion = Get-ChildItem -LiteralPath "$taskSdk\Include" -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' -and (Test-Path -LiteralPath "$($_.FullName)\um\Windows.h") } |
    Sort-Object { [Version]$_.Name } -Descending | Select-Object -First 1 -ExpandProperty Name
if (!$taskSdkVersion) { throw 'No complete Windows SDK found.' }
$taskOldPath=$env:PATH; $taskOldInclude=$env:INCLUDE; $taskOldLib=$env:LIB
$taskOut = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
Push-Location -LiteralPath $taskOut
try {
    $env:PATH="$taskVc\bin\Hostx64\x86;$env:PATH"
    $env:INCLUDE="$taskVc\include;$taskSdk\Include\$taskSdkVersion\ucrt;$taskSdk\Include\$taskSdkVersion\shared;$taskSdk\Include\$taskSdkVersion\um"
    $env:LIB="$taskVc\lib\x86;$taskSdk\Lib\$taskSdkVersion\ucrt\x86;$taskSdk\Lib\$taskSdkVersion\um\x86"
    $taskSources = @('src/realtime.cpp','src/proxy.cpp','vendor/minhook/src/buffer.c','vendor/minhook/src/hook.c','vendor/minhook/src/trampoline.c','vendor/minhook/src/hde/hde32.c') |
        ForEach-Object { Join-Path $PSScriptRoot $_ }
    & "$taskVc\bin\Hostx64\x86\cl.exe" /nologo /LD /O2 /MT /W4 /EHsc "/I$PSScriptRoot\vendor\minhook\include" /Fe:d3d9.dll @taskSources /link "/DEF:$PSScriptRoot\src\proxy.def" /INCREMENTAL:NO /DYNAMICBASE /NXCOMPAT
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $LASTEXITCODE" }
} finally {
    Pop-Location
    $env:PATH=$taskOldPath; $env:INCLUDE=$taskOldInclude; $env:LIB=$taskOldLib
}
$taskBuilt = Get-Item -LiteralPath "$taskOut\d3d9.dll"
Write-Output "Built: $($taskBuilt.FullName) ($($taskBuilt.Length) bytes)"
Write-Output "SHA256: $((Get-FileHash -LiteralPath $taskBuilt.FullName -Algorithm SHA256).Hash)"
