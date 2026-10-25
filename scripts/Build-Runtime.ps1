param(
    [string]$OutputRoot = ".\artifacts\runtime",
    [string]$MsvcToolRoot = "",
    [string]$WindowsSdkRoot = "",
    [switch]$FreestyleDiagnosticParity,
    [switch]$FreestyleDiagnosticNamedRetention,
    [switch]$SiegeCrashDiagnostic,
    [switch]$ExplorationTests,
    [switch]$FeatureTests,
    [switch]$RegistrationTests,
    [switch]$RegistrationDiagnostic
)

$ErrorActionPreference = "Stop"
if ($RegistrationTests) {
    foreach ($name in @("MAJESTY_PUBLIC_EXE", "MAJESTY_BETA2_EXE", "MAJESTY_GOG_EXE", "MAJESTY_BCD_GAME", "MAJESTY_BCD_GOG_GAME")) {
        $fixturePath = [Environment]::GetEnvironmentVariable($name)
        $fixtureType = if ($name -like '*_GAME') { 'Container' } else { 'Leaf' }
        if (-not $fixturePath -or -not (Test-Path -LiteralPath $fixturePath -PathType $fixtureType)) {
            throw "Three-version runtime verification requires $name. No skipped profiles are allowed."
        }
    }
}
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
if ($RegistrationDiagnostic) {
    $runtimeDefines += "/DMAJESTY_REGISTRATION_DIAGNOSTIC=1"
}
if ($FreestyleDiagnosticNamedRetention) {
    $runtimeDefines += "/DFREESTYLE_CAM_DIAGNOSTIC_NAMED_RETENTION=1"
} elseif ($FreestyleDiagnosticParity) {
    $runtimeDefines += "/DFREESTYLE_CAM_DIAGNOSTIC_PARITY=1"
}
if ($SiegeCrashDiagnostic) {
    $runtimeDefines += "/DCAM_SIEGE_CRASH_DIAGNOSTIC=1"
}

$runtimeSources = @(
    (Join-Path $sourceRoot "BooleanRuntime.cpp"),
    (Join-Path $sourceRoot "NativeImpactRegistry.cpp"),
    (Join-Path $sourceRoot "NativeImpactRuntime.cpp"),
    (Join-Path $sourceRoot "AttackObservation.cpp"),
    (Join-Path $sourceRoot "AttackObservationProof.cpp"),
    (Join-Path $sourceRoot "EquipmentRuntime.cpp"),
    (Join-Path $sourceRoot "BoundedMapQuery.cpp"),
    (Join-Path $sourceRoot "MapQueryRuntime.cpp"),
    (Join-Path $sourceRoot "PaidSourceTargetCommand.cpp"),
    (Join-Path $sourceRoot "MajestyModManagerRuntime.cpp"),
    (Join-Path $sourceRoot "ControllerLifecycleRegistry.cpp"),
    (Join-Path $sourceRoot "FreestyleCamRuntime.cpp"),
    (Join-Path $sourceRoot "IntentTextRegistry.cpp"),
    (Join-Path $sourceRoot "RuntimeCapabilityManifest.cpp"),
    (Join-Path $sourceRoot "RuntimeFeatureRegistry.cpp"),
    (Join-Path $sourceRoot "StockControllerRegistry.cpp")
)
$runtimeLibraries = @("user32.lib", "bcrypt.lib")
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

$fixtureNames = @()
if ($ExplorationTests) { $fixtureNames += "ExplorationNativeTests" }
if ($FeatureTests) { $fixtureNames += "OccupantActionRuntimeTests"; $fixtureNames += "NativeImpactReleaseTests"; $fixtureNames += "RegistrationDiagnosticTests" }
if ($FeatureTests) { $fixtureNames += "PaidSourceTargetCommandTests", "PanelLifecycleRuntimeTests" }
if ($RegistrationTests) { $fixtureNames += "SharedRegistrationRuntimeTests"; $fixtureNames += "NativeRegistrationLifecycleTests" }
foreach ($fixtureName in $fixtureNames) {
    $fixtureLinkOptions = @()
    $fixtureArguments = @()
    $fixedImageFixture = $fixtureName -in @("SharedRegistrationRuntimeTests", "NativeRegistrationLifecycleTests")
    if ($fixedImageFixture) {
        # Reserve the game image's preferred base for nonexecuted fixture bytes.
        $fixtureLinkOptions = @("/BASE:0x10000000", "/ALIGN:65536", "/DYNAMICBASE:NO")
        $fixtureArguments = @($env:MAJESTY_PUBLIC_EXE, $env:MAJESTY_BETA2_EXE, $env:MAJESTY_GOG_EXE)
    }
    $fixtureSources = @($runtimeSources | Where-Object { [IO.Path]::GetFileName($_) -ne "MajestyModManagerRuntime.cpp" })
    if ($fixtureName -eq "NativeRegistrationLifecycleTests") {
        $fixtureSources = @("AttackObservation.cpp", "AttackObservationProof.cpp", "NativeImpactRegistry.cpp") |
            ForEach-Object { Join-Path $sourceRoot $_ }
    }
    if ($RegistrationTests -and $fixedImageFixture) {
        $fixtureSources += (Join-Path $repoRoot "tests\GogFixtureMemory.cpp")
    }
    & $compiler /nologo /W4 /O2 /EHsc @commonIncludes @runtimeDefines `
        @fixtureSources (Join-Path $repoRoot "tests\$fixtureName.cpp") `
        "/Fo$output\" "/Fe:$output\$fixtureName.exe" /link @commonLibPaths @runtimeLibraries @fixtureLinkOptions
    if ($LASTEXITCODE -ne 0) { throw "$fixtureName build failed" }
    if ($fixedImageFixture) {
        # Same fixed-address, data-only fixture layout used by GOG profile tests.
        $testExe = Join-Path $output "$fixtureName.exe"
        $testBytes = [IO.File]::ReadAllBytes($testExe)
        $peOffset = [BitConverter]::ToInt32($testBytes, 0x3C)
        $count = [BitConverter]::ToUInt16($testBytes, $peOffset + 6)
        $table = $peOffset + 24 + [BitConverter]::ToUInt16($testBytes, $peOffset + 20)
        $fixtureRva = 0
        for ($i = 0; $i -lt $count; $i++) {
            $offset = $table + 40 * $i
            if ([Text.Encoding]::ASCII.GetString($testBytes, $offset, 8) -eq '.fixture') {
                $fixtureRva = [BitConverter]::ToUInt32($testBytes, $offset + 12)
            }
        }
        if ($fixtureRva -eq 0 -or $fixtureRva -ge 0x400000 -or ($fixtureRva % 65536) -ne 0) {
            throw "Invalid registration fixture section"
        }
        $testBase = '0x{0:X}' -f (0x400000 - $fixtureRva)
        $objects = @($fixtureSources | ForEach-Object { Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($_)) + '.obj') })
        $objects += (Join-Path $output "$fixtureName.obj")
        & $compiler /nologo @objects "/Fe:$testExe" /link "/BASE:$testBase" /ALIGN:65536 /DYNAMICBASE:NO @commonLibPaths @runtimeLibraries
        if ($LASTEXITCODE -ne 0) { throw "Registration fixture layout did not link" }
    }
    if ($fixtureName -eq "NativeRegistrationLifecycleTests") {
        for ($profileIndex = 0; $profileIndex -lt 3; $profileIndex++) {
            & (Join-Path $output "$fixtureName.exe") $fixtureArguments[$profileIndex] $profileIndex
            if ($LASTEXITCODE -ne 0) { throw "$fixtureName failed for profile $profileIndex" }
        }
    } else {
        & (Join-Path $output "$fixtureName.exe") @fixtureArguments
        if ($LASTEXITCODE -ne 0) { throw "$fixtureName failed" }
    }
    if ($fixtureName -eq "RegistrationDiagnosticTests") {
        # Prove the normal release build cannot emit these diagnostics.
        & $compiler /nologo /W4 /O2 /EHsc @commonIncludes `
            (Join-Path $repoRoot "tests\RegistrationDiagnosticTests.cpp") `
            "/Fo$output\RegistrationDiagnosticDisabled.obj" "/Fe:$output\RegistrationDiagnosticDisabled.exe" /link @commonLibPaths
        if ($LASTEXITCODE -ne 0) { throw "Disabled registration diagnostic fixture build failed" }
        & (Join-Path $output "RegistrationDiagnosticDisabled.exe")
        if ($LASTEXITCODE -ne 0) { throw "Disabled registration diagnostic emitted output" }
    }
}

if ($RegistrationTests -and $FeatureTests -and $ExplorationTests) {
    $receipt = @{
        schema = 1
        verification = "offline-native-installation-and-lifecycle-fixtures"
        liveGameplayAcceptance = $false
        runtimeSha256 = (Get-FileHash -LiteralPath (Join-Path $output "MajestyBuildingRuntime.dll") -Algorithm SHA256).Hash
        profiles = @{}
    }
    foreach ($name in @("MAJESTY_PUBLIC_EXE", "MAJESTY_BETA2_EXE", "MAJESTY_GOG_EXE")) {
        $receipt.profiles[$name] = (Get-FileHash -LiteralPath ([Environment]::GetEnvironmentVariable($name)) -Algorithm SHA256).Hash
    }
    $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output "runtime-parity.json") -Encoding UTF8
}
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
