param(
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD",
    [string]$InputRoot,
    [string]$OutputRoot,
    [string]$RuntimeOutputRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $InputRoot) {
    $InputRoot = Join-Path $repoRoot "local\poc\inputs"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "local\poc\freestyle-haunt-output-v1"
}
$workspaceRoot = Split-Path -Parent $repoRoot
$python = Join-Path $workspaceRoot ".tools\python.cmd"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Workspace Python wrapper was not found: $python"
}
$runtimeBuild = Join-Path $repoRoot "scripts\Build-Runtime.ps1"
if (-not $RuntimeOutputRoot) {
    $RuntimeOutputRoot = Join-Path $repoRoot "local\runtime-freestyle-validation"
}
if (-not (Test-Path -LiteralPath $runtimeBuild -PathType Leaf)) {
    throw "CAM Manager runtime build script was not found: $runtimeBuild"
}

& $runtimeBuild -OutputRoot $RuntimeOutputRoot
if ($LASTEXITCODE -ne 0) {
    throw "CAM Manager runtime build failed with exit code $LASTEXITCODE"
}

$savedPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $repoRoot "src"
try {
    & $python -m majesty_cam.cli haunt-poc-build `
        --game-path $GamePath `
        --input-root $InputRoot `
        --output-root $OutputRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Haunt Freestyle POC build failed with exit code $LASTEXITCODE"
    }
}
finally {
    $env:PYTHONPATH = $savedPythonPath
}
