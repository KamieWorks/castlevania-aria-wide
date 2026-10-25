param(
    [string]$PackageName='AriaWide-v26-release',
    [string]$OutputDirectory=(Join-Path $PSScriptRoot '../deliverables'),
    [string]$DllPath=(Join-Path $PSScriptRoot 'build/d3d9.dll'),
    [switch]$IncludeSource
)
$ErrorActionPreference='Stop'
if ($PackageName -notmatch '^AriaWide-[a-zA-Z0-9.-]+$') { throw 'Use a simple AriaWide package name.' }
$taskRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$taskOutput=[IO.Path]::GetFullPath($OutputDirectory)
$taskBinary=[IO.Path]::GetFullPath($DllPath)
if (!(Test-Path -LiteralPath $taskBinary -PathType Leaf)) { throw 'Build d3d9.dll first.' }
$taskPlayer=Join-Path $taskOutput $PackageName
$taskSource=Join-Path $taskOutput "$PackageName-source"
$taskTargets=@($taskPlayer,"$taskPlayer.zip")
if ($IncludeSource) { $taskTargets+=@($taskSource,"$taskSource.zip") }
foreach ($taskPath in $taskTargets) {
    if (Test-Path -LiteralPath $taskPath) { throw "Refusing to overwrite: $taskPath" }
}
New-Item -ItemType Directory -Path $taskPlayer -Force | Out-Null
Copy-Item -LiteralPath $taskBinary -Destination (Join-Path $taskPlayer 'd3d9.dll')
Copy-Item -LiteralPath (Join-Path $taskRoot 'README.release.txt') -Destination (Join-Path $taskPlayer 'README.txt')
$taskLicense=[IO.File]::ReadAllText((Join-Path $taskRoot 'vendor/minhook/LICENSE.txt'))
$taskReadme=[IO.File]::ReadAllText((Join-Path $taskPlayer 'README.txt'))
if (!$taskReadme.Contains($taskLicense)) { throw 'The release README must retain the complete third-party license.' }
Compress-Archive -LiteralPath (Get-ChildItem -LiteralPath $taskPlayer -File).FullName -DestinationPath "$taskPlayer.zip" -CompressionLevel Optimal
Write-Output "Player package: $taskPlayer.zip (d3d9.dll + README.txt)"
if ($IncludeSource) {
    New-Item -ItemType Directory -Path $taskSource -Force | Out-Null
    $taskFiles=@(Get-ChildItem -LiteralPath (Join-Path $taskRoot 'src'),(Join-Path $taskRoot 'vendor') -Recurse -File)
    foreach ($taskName in @('AriaWide.ini','README.zh-CN.md','README.release.txt','VALIDATION.zh-CN.md','THIRD-PARTY.md','build.ps1','package.ps1')) {
        $taskFiles+=Get-Item -LiteralPath (Join-Path $taskRoot $taskName)
    }
    foreach ($taskFile in $taskFiles) {
        $taskRelative=$taskFile.FullName.Substring($taskRoot.Length+1)
        $taskDestination=Join-Path $taskSource $taskRelative
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($taskDestination)) -Force | Out-Null
        Copy-Item -LiteralPath $taskFile.FullName -Destination $taskDestination
    }
    Compress-Archive -LiteralPath (Get-ChildItem -LiteralPath $taskSource -Force).FullName -DestinationPath "$taskSource.zip" -CompressionLevel Optimal
    Write-Output "Build source package: $taskSource.zip"
}
Write-Output "DLL SHA256: $((Get-FileHash -LiteralPath $taskBinary -Algorithm SHA256).Hash.ToLowerInvariant())"
Write-Output "ZIP SHA256: $((Get-FileHash -LiteralPath "$taskPlayer.zip" -Algorithm SHA256).Hash.ToLowerInvariant())"
