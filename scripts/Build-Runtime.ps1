param(
    [string]$OutputRoot = ".\artifacts\runtime",
    [switch]$FreestyleDiagnosticParity,
    [switch]$FreestyleDiagnosticNamedRetention,
    [switch]$SiegeCrashDiagnostic
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $repoRoot "runtime"
$output = if ([IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot
} else {
    Join-Path $repoRoot $OutputRoot
}
$toolRoot = "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023"
$compiler = Join-Path $toolRoot "bin\Hostx86\x86\cl.exe"
$include = Join-Path $toolRoot "include"
$windowsSdk = "C:\Program Files (x86)\Windows Kits\10"
$sdkIncludeVersion = Get-ChildItem (Join-Path $windowsSdk "Include") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
$sdkLibVersion = Get-ChildItem (Join-Path $windowsSdk "Lib") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "x86 MSVC compiler was not found: $compiler"
}
if ($null -eq $sdkIncludeVersion -or $null -eq $sdkLibVersion) {
    throw "Windows SDK include/lib directories were not found."
}
New-Item -ItemType Directory -Path $output -Force | Out-Null

$commonIncludes = @(
    "/I$include",
    "/I$($sdkIncludeVersion.FullName)\ucrt",
    "/I$($sdkIncludeVersion.FullName)\shared",
    "/I$($sdkIncludeVersion.FullName)\um"
)
$commonLibPaths = @(
    "/LIBPATH:$toolRoot\lib\x86",
    "/LIBPATH:$($sdkLibVersion.FullName)\ucrt\x86",
    "/LIBPATH:$($sdkLibVersion.FullName)\um\x86"
)

$runtimeDefines = @()
if ($FreestyleDiagnosticNamedRetention) {
    $runtimeDefines += "/DFREESTYLE_CAM_DIAGNOSTIC_NAMED_RETENTION=1"
} elseif ($FreestyleDiagnosticParity) {
    $runtimeDefines += "/DFREESTYLE_CAM_DIAGNOSTIC_PARITY=1"
}
if ($SiegeCrashDiagnostic) {
    $runtimeDefines += "/DCAM_SIEGE_CRASH_DIAGNOSTIC=1"
}

$runtimeSources = @(
    (Join-Path $sourceRoot "MajestyModManagerRuntime.cpp"),
    (Join-Path $sourceRoot "ControllerLifecycleRegistry.cpp"),
    (Join-Path $sourceRoot "FreestyleCamRuntime.cpp"),
    (Join-Path $sourceRoot "IntentTextRegistry.cpp"),
    (Join-Path $sourceRoot "RuntimeCapabilityManifest.cpp"),
    (Join-Path $sourceRoot "RuntimeFeatureRegistry.cpp"),
    (Join-Path $sourceRoot "StockControllerRegistry.cpp")
)
$runtimeLibraries = @("user32.lib")
if ($SiegeCrashDiagnostic) {
    $runtimeSources += (Join-Path $sourceRoot "CrashDumpDiagnostic.cpp")
    $runtimeLibraries += "dbghelp.lib"
}

& $compiler /nologo /W4 /O2 /EHsc /LD @commonIncludes @runtimeDefines `
    @runtimeSources `
    "/Fo$output\" "/Fe:$output\MajestyBuildingRuntime.dll" /link @commonLibPaths @runtimeLibraries
if ($LASTEXITCODE -ne 0) { throw "Runtime DLL build failed with exit code $LASTEXITCODE" }

& $compiler /nologo /W4 /O2 /EHsc @commonIncludes `
    (Join-Path $sourceRoot "MajestyBuildingRuntimeLauncher.cpp") `
    "/Fo$output\" "/Fe:$output\MajestyBuildingRuntimeLauncher.exe" /link @commonLibPaths
if ($LASTEXITCODE -ne 0) { throw "Runtime launcher build failed with exit code $LASTEXITCODE" }

Write-Host "Built x86 Majesty Mod Manager native runtime:"
Write-Host $output
if ($FreestyleDiagnosticNamedRetention) {
    Write-Host "Freestyle mode: named-wrapper retention diagnostic"
} elseif ($FreestyleDiagnosticParity) {
    Write-Host "Freestyle mode: upstream-parity diagnostic"
}
if ($SiegeCrashDiagnostic) {
    Write-Host "Crash mode: full-memory capture for the diagnosed Siege GPL evaluator fault"
}
