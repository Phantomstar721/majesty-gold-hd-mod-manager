param(
    [string]$OutputDir = "",
    [switch]$KeepBuildFiles
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$work = Join-Path $repoRoot "local\pyinstaller"
$payloadMarker = Join-Path $repoRoot "payload\.majesty-mod-manager-payload"
$assetRoot = Join-Path $repoRoot "src\majesty_cam\manager\assets"
$managerIcon = Join-Path $assetRoot "manager-icon.ico"
$requiredPayloadFiles = @(
    "payload\runtime\MajestyBuildingRuntimeLauncher.exe",
    "payload\runtime\MajestyBuildingRuntime.dll",
    "payload\runtime\LICENSE-expanded-building-runtime.txt",
    "payload\qol\generic-visitor-lists\Install-GenericVisitorLists.ps1",
    "payload\qol\generic-visitor-lists\MajestyBuildProfiles.ps1",
    "payload\qol\generic-visitor-lists\LICENSE.txt",
    "payload\qol\remember-active-mods\Install-ModPersistence.ps1",
    "payload\qol\remember-active-mods\MajestyBuildProfiles.ps1",
    "payload\qol\remember-active-mods\NativePathEncoding.ps1",
    "payload\qol\remember-active-mods\LICENSE.txt",
    "payload\qol\LICENSE-qol-utilities.txt",
    "payload\qol\utilities\Generic Visitor Lists\scripts\Install-GenericVisitorLists.ps1",
    "payload\qol\utilities\Remember Active Mods\scripts\Install-ModPersistence.ps1",
    "payload\mods\CustomGuildPhantomsHauntExpanded\CustomGuildPhantomsHaunt.mmxml"
)
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "dist"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Run Setup - Majesty Mod Manager.bat before building the standalone app."
}
if (-not (Test-Path -LiteralPath $managerIcon -PathType Leaf)) {
    throw "The Majesty Mod Manager icon was not found: $managerIcon"
}
$releaseFiles = @(
    (Join-Path $repoRoot "LICENSE"),
    (Join-Path $repoRoot "THIRD-PARTY-NOTICES.md"),
    (Join-Path $repoRoot "licenses\PYTHON-3.9.txt"),
    (Join-Path $repoRoot "licenses\LGPL-3.0.txt"),
    (Join-Path $repoRoot "licenses\GPL-3.0.txt"),
    (Join-Path $repoRoot "licenses\PYINSTALLER.txt"),
    (Join-Path $assetRoot "STEAM-ICON-NOTICE.txt")
)
foreach ($releaseFile in $releaseFiles) {
    if (-not (Test-Path -LiteralPath $releaseFile -PathType Leaf)) {
        throw "Required release notice was not found: $releaseFile"
    }
}
$payloadCurrent = (Test-Path -LiteralPath $payloadMarker -PathType Leaf) -and `
    ((Get-Content -LiteralPath $payloadMarker -Raw).Trim() -eq "schema=2")
if ($payloadCurrent) {
    foreach ($relative in $requiredPayloadFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $relative) -PathType Leaf)) {
            $payloadCurrent = $false
            break
        }
    }
}
if (-not $payloadCurrent) {
    & (Join-Path $PSScriptRoot "Stage-ModManagerPayload.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stage a complete schema-2 manager payload."
    }
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --disable-pip-version-check -e "$repoRoot[package]"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the standalone packager."
    }
}

$arguments = @(
    "-m", "PyInstaller",
    # Keep the bundled runtime and patch scripts beside the executable for the
    # entire game session.  A one-file build extracts them to a temporary
    # directory that can disappear if the manager window closes after launch.
    "--noconfirm", "--clean", "--onedir", "--windowed", "--uac-admin", "--noupx",
    "--name", "Majesty Mod Manager",
    "--icon", $managerIcon,
    "--distpath", $OutputDir,
    "--workpath", $work,
    "--specpath", $work,
    "--paths", (Join-Path $repoRoot "src"),
    "--add-data", ((Join-Path $repoRoot "payload") + ";payload"),
    "--add-data", ((Join-Path $repoRoot "profiles") + ";profiles"),
    "--add-data", ((Join-Path $repoRoot "src\majesty_cam\manager\theme.qss") + ";majesty_cam\manager")
)
if (Test-Path -LiteralPath $assetRoot -PathType Container) {
    $arguments += @("--add-data", ($assetRoot + ";majesty_cam\manager\assets"))
}
$arguments += (Join-Path $PSScriptRoot "mod_manager_entry.py")

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}
$applicationOutput = Join-Path $OutputDir "Majesty Mod Manager"
$applicationLicenses = Join-Path $applicationOutput "licenses"
New-Item -ItemType Directory -Path $applicationLicenses -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $applicationOutput "LICENSE.txt") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "THIRD-PARTY-NOTICES.md") -Destination $applicationOutput -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "licenses\PYTHON-3.9.txt") -Destination $applicationLicenses -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "licenses\LGPL-3.0.txt") -Destination $applicationLicenses -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "licenses\GPL-3.0.txt") -Destination $applicationLicenses -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "licenses\PYINSTALLER.txt") -Destination $applicationLicenses -Force
Copy-Item -LiteralPath (Join-Path $assetRoot "STEAM-ICON-NOTICE.txt") -Destination $applicationLicenses -Force
if (-not $KeepBuildFiles) {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "Built standalone windowed app:"
Write-Host (Join-Path $applicationOutput "Majesty Mod Manager.exe")
