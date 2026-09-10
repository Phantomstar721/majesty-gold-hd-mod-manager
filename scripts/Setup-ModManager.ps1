param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $repoRoot
$workspacePython = Join-Path $workspaceRoot ".tools\python.cmd"
$venvRoot = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$payloadMarker = Join-Path $repoRoot "payload\.majesty-mod-manager-payload"
$requiredPayloadFiles = @(
    "payload\runtime\MajestyBuildingRuntimeLauncher.exe",
    "payload\runtime\MajestyBuildingRuntime.dll",
    "payload\runtime\LICENSE-manager-runtime.txt",
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

$pythonCommand = ""
$pythonArguments = @()
if (Test-Path -LiteralPath $workspacePython -PathType Leaf) {
    $pythonCommand = $workspacePython
}
else {
    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        $pythonCommand = $pyLauncher.Source
        $pythonArguments = @("-3")
    }
    else {
        $systemPython = Get-Command "python.exe" -ErrorAction SilentlyContinue
        if ($null -ne $systemPython) {
            $pythonCommand = $systemPython.Source
        }
    }
}
if (-not $pythonCommand) {
    throw "Python 3.9 or newer was not found. Install Python, then run Setup again."
}
& $pythonCommand @pythonArguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The available Python is older than 3.9. Install Python 3.9 or newer, then run Setup again."
}
$payloadCurrent = (Test-Path -LiteralPath $payloadMarker -PathType Leaf) -and `
    ((Get-Content -LiteralPath $payloadMarker -Raw).Trim() -eq "schema=3")
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
        throw "Could not stage the complete manager runtime and QOL payload."
    }
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $pythonCommand @pythonArguments -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the Majesty Mod Manager environment."
    }
}

& $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv uses Python older than 3.9. Remove that environment and run Setup again."
}

& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not update pip in the manager environment."
}
& $venvPython -m pip install --disable-pip-version-check -e "$repoRoot[gui]"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the Majesty Mod Manager GUI dependencies."
}

Write-Host "Majesty Mod Manager is ready."
Write-Host "Double-click Launch - Majesty Mod Manager.bat."
