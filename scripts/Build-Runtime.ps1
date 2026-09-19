param(
    [string]$OutputRoot = ".\artifacts\runtime",
    [string]$MsvcToolRoot = "",
    [string]$WindowsSdkRoot = "",
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
function Find-MsvcToolRoot {
    param([string]$RequestedRoot)

    if ($RequestedRoot) {
        $candidate = [IO.Path]::GetFullPath($RequestedRoot)
        if (Test-Path -LiteralPath (Join-Path $candidate "bin\Hostx86\x86\cl.exe") -PathType Leaf) {
            return $candidate
        }
        throw "The requested x86 MSVC tool root is invalid: $candidate"
    }

    $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    $installations = @()
    $vswhere = Join-Path $programFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $found = & $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0) {
            $installations += @($found | Where-Object { $_ })
        }
    }
    $visualStudioRoot = Join-Path $programFilesX86 "Microsoft Visual Studio"
    if (Test-Path -LiteralPath $visualStudioRoot -PathType Container) {
        foreach ($year in Get-ChildItem -LiteralPath $visualStudioRoot -Directory) {
            foreach ($edition in Get-ChildItem -LiteralPath $year.FullName -Directory) {
                $installations += $edition.FullName
            }
        }
    }
    $candidates = @()
    foreach ($installation in $installations | Select-Object -Unique) {
        $versions = Join-Path $installation "VC\Tools\MSVC"
        if (-not (Test-Path -LiteralPath $versions -PathType Container)) {
            continue
        }
        foreach ($candidate in Get-ChildItem -LiteralPath $versions -Directory) {
            if (Test-Path -LiteralPath (Join-Path $candidate.FullName "bin\Hostx86\x86\cl.exe") -PathType Leaf) {
                $candidates += $candidate
            }
        }
    }
    $selected = $candidates |
        Sort-Object @{ Expression = { [version]$_.Name }; Descending = $true } |
        Select-Object -First 1
    if ($null -ne $selected) {
        return $selected.FullName
    }
    throw "An x86 Visual C++ compiler was not found. Install the Visual Studio C++ build tools."
}

$toolRoot = Find-MsvcToolRoot $MsvcToolRoot
$compiler = Join-Path $toolRoot "bin\Hostx86\x86\cl.exe"
$include = Join-Path $toolRoot "include"
$windowsSdk = if ($WindowsSdkRoot) {
    [IO.Path]::GetFullPath($WindowsSdkRoot)
} else {
    Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10"
}
$sdkVersion = Get-ChildItem (Join-Path $windowsSdk "Include") -Directory |
    Sort-Object Name -Descending |
    Where-Object {
        (Test-Path -LiteralPath (Join-Path $_.FullName "ucrt") -PathType Container) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName "shared") -PathType Container) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName "um") -PathType Container) -and
        (Test-Path -LiteralPath (Join-Path $windowsSdk "Lib\$($_.Name)\ucrt\x86") -PathType Container) -and
        (Test-Path -LiteralPath (Join-Path $windowsSdk "Lib\$($_.Name)\um\x86") -PathType Container)
    } |
    Select-Object -First 1

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "x86 MSVC compiler was not found: $compiler"
}
if ($null -eq $sdkVersion) {
    throw "A complete x86 Windows 10 SDK include/lib version was not found under $windowsSdk."
}
New-Item -ItemType Directory -Path $output -Force | Out-Null

$commonIncludes = @(
    "/I$include",
    "/I$($sdkVersion.FullName)\ucrt",
    "/I$($sdkVersion.FullName)\shared",
    "/I$($sdkVersion.FullName)\um"
)
$commonLibPaths = @(
    "/LIBPATH:$toolRoot\lib\x86",
    "/LIBPATH:$windowsSdk\Lib\$($sdkVersion.Name)\ucrt\x86",
    "/LIBPATH:$windowsSdk\Lib\$($sdkVersion.Name)\um\x86"
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
    (Join-Path $sourceRoot "EquipmentRuntime.cpp"),
    (Join-Path $sourceRoot "BoundedMapQuery.cpp"),
    (Join-Path $sourceRoot "MapQueryRuntime.cpp"),
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
