param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $repoRoot
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "payload"
}
$target = [IO.Path]::GetFullPath($OutputRoot)
$expected = [IO.Path]::GetFullPath((Join-Path $repoRoot "payload"))
if ($target -ne $expected) {
    throw "Payload staging is restricted to the manager-owned path: $expected"
}

$stage = Join-Path $repoRoot (".payload-stage-" + [guid]::NewGuid().ToString("N"))
$backup = Join-Path $repoRoot (".payload-backup-" + [guid]::NewGuid().ToString("N"))
$runtimeSource = Join-Path $workspaceRoot "majesty-gold-hd-expanded-building-slots\artifacts\runtime-intent-text"
$visitorRepo = Join-Path $workspaceRoot "majesty-gold-hd-generic-visitor-lists"
$rememberRepo = Join-Path $workspaceRoot "majesty-gold-hd-remember-active-mods"
$qolRepo = Join-Path $workspaceRoot "majesty-gold-hd-qol-utilities"
$hauntSource = Join-Path $workspaceRoot "majesty-gold-hd-custom-guild-phantoms-haunt\dist\CustomGuildPhantomsHauntExpanded"

$required = @(
    (Join-Path $runtimeSource "MajestyBuildingRuntimeLauncher.exe"),
    (Join-Path $runtimeSource "MajestyBuildingRuntime.dll"),
    (Join-Path $visitorRepo "scripts\Install-GenericVisitorLists.ps1"),
    (Join-Path $visitorRepo "scripts\MajestyBuildProfiles.ps1"),
    (Join-Path $rememberRepo "scripts\Install-ModPersistence.ps1"),
    (Join-Path $rememberRepo "scripts\MajestyBuildProfiles.ps1"),
    (Join-Path $rememberRepo "scripts\NativePathEncoding.ps1"),
    (Join-Path $qolRepo "LICENSE"),
    (Join-Path $qolRepo "utilities\Generic Visitor Lists\scripts\Install-GenericVisitorLists.ps1"),
    (Join-Path $qolRepo "utilities\Remember Active Mods\scripts\Install-ModPersistence.ps1"),
    (Join-Path $hauntSource "CustomGuildPhantomsHaunt.mmxml")
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required manager payload input was not found: $path"
    }
}

try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    Set-Content -LiteralPath (Join-Path $stage ".majesty-mod-manager-payload") -Value "schema=2" -Encoding ASCII

    $runtimeTarget = Join-Path $stage "runtime"
    New-Item -ItemType Directory -Path $runtimeTarget | Out-Null
    Copy-Item -LiteralPath (Join-Path $runtimeSource "MajestyBuildingRuntimeLauncher.exe") -Destination $runtimeTarget
    Copy-Item -LiteralPath (Join-Path $runtimeSource "MajestyBuildingRuntime.dll") -Destination $runtimeTarget
    Copy-Item -LiteralPath (Join-Path $workspaceRoot "majesty-gold-hd-expanded-building-slots\LICENSE") -Destination (Join-Path $runtimeTarget "LICENSE-expanded-building-runtime.txt")

    $visitorTarget = Join-Path $stage "qol\generic-visitor-lists"
    New-Item -ItemType Directory -Path $visitorTarget | Out-Null
    Copy-Item -LiteralPath (Join-Path $visitorRepo "scripts\Install-GenericVisitorLists.ps1") -Destination $visitorTarget
    Copy-Item -LiteralPath (Join-Path $visitorRepo "scripts\MajestyBuildProfiles.ps1") -Destination $visitorTarget
    Copy-Item -LiteralPath (Join-Path $visitorRepo "LICENSE") -Destination (Join-Path $visitorTarget "LICENSE.txt")

    $rememberTarget = Join-Path $stage "qol\remember-active-mods"
    New-Item -ItemType Directory -Path $rememberTarget | Out-Null
    Copy-Item -LiteralPath (Join-Path $rememberRepo "scripts\Install-ModPersistence.ps1") -Destination $rememberTarget
    Copy-Item -LiteralPath (Join-Path $rememberRepo "scripts\MajestyBuildProfiles.ps1") -Destination $rememberTarget
    Copy-Item -LiteralPath (Join-Path $rememberRepo "scripts\NativePathEncoding.ps1") -Destination $rememberTarget
    Copy-Item -LiteralPath (Join-Path $rememberRepo "LICENSE") -Destination (Join-Path $rememberTarget "LICENSE.txt")

    # Bundle the complete MIT-licensed QoL suite.  Its installers use the same
    # guarded bytes and private sections as the standalone application, so an
    # existing standalone installation is detected rather than applied twice.
    $qolTarget = Join-Path $stage "qol\utilities"
    New-Item -ItemType Directory -Path (Split-Path -Parent $qolTarget) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $qolRepo "utilities") -Destination $qolTarget -Recurse
    Copy-Item -LiteralPath (Join-Path $qolRepo "LICENSE") -Destination (Join-Path $stage "qol\LICENSE-qol-utilities.txt")

    $modsTarget = Join-Path $stage "mods\CustomGuildPhantomsHauntExpanded"
    New-Item -ItemType Directory -Path (Split-Path -Parent $modsTarget) | Out-Null
    Copy-Item -LiteralPath $hauntSource -Destination $modsTarget -Recurse

    if (Test-Path -LiteralPath $target) {
        if (-not (Test-Path -LiteralPath (Join-Path $target ".majesty-mod-manager-payload") -PathType Leaf)) {
            throw "Refusing to replace a payload directory not owned by Majesty Mod Manager: $target"
        }
        Move-Item -LiteralPath $target -Destination $backup
    }
    Move-Item -LiteralPath $stage -Destination $target
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
}
catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}

Write-Host "Staged Majesty Mod Manager runtime, complete QOL suite, and improved Haunt input:"
Write-Host $target
