$ErrorActionPreference='Stop'
function Initialize-AriaToolchain {
    $taskVswhere="${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (!(Test-Path -LiteralPath $taskVswhere)) { throw 'Install Visual Studio C++ x86 build tools and a Windows SDK.' }
    $taskVsRoot=(& $taskVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if (!$taskVsRoot) { throw 'No MSVC C++ x86 toolchain found.' }
    $taskVersion=(Get-Content -LiteralPath "$taskVsRoot\VC\Auxiliary\Build\Microsoft.VCToolsVersion.default.txt" -Raw).Trim()
    $taskVc="$taskVsRoot\VC\Tools\MSVC\$taskVersion"
    $taskSdk=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' -ErrorAction SilentlyContinue).KitsRoot10
    if (!$taskSdk) { $taskSdk=(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots').KitsRoot10 }
    $taskSdkVersion=Get-ChildItem -LiteralPath "$taskSdk\Include" -Directory | Where-Object { $_.Name -match '^\d+\.\d+\.\d+\.\d+$' -and (Test-Path -LiteralPath "$($_.FullName)\um\Windows.h") } | Sort-Object { [Version]$_.Name } -Descending | Select-Object -First 1 -ExpandProperty Name
    if (!$taskSdkVersion) { throw 'No complete Windows SDK found.' }
    $env:PATH="$taskVc\bin\Hostx64\x86;$env:PATH"
    $env:INCLUDE="$taskVc\include;$taskSdk\Include\$taskSdkVersion\ucrt;$taskSdk\Include\$taskSdkVersion\shared;$taskSdk\Include\$taskSdkVersion\um"
    $env:LIB="$taskVc\lib\x86;$taskSdk\Lib\$taskSdkVersion\ucrt\x86;$taskSdk\Lib\$taskSdkVersion\um\x86"
    return "$taskVc\bin\Hostx64\x86\cl.exe"
}
function Get-AriaDebugRoot {
    if ($env:ARIA_DEBUG_ROOT) { return [IO.Path]::GetFullPath($env:ARIA_DEBUG_ROOT) }
    return [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../out/debug'))
}
