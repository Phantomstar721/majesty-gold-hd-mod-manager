param(
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD",
    [string]$InputRoot,
    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $InputRoot) {
    $InputRoot = Join-Path $repoRoot "local\poc\inputs"
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "local\poc\rebuild-outputs"
}
$workspaceRoot = Split-Path -Parent $repoRoot
$python = Join-Path $workspaceRoot ".tools\python.cmd"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Workspace Python wrapper was not found: $python"
}

$savedPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $repoRoot "src"
try {
    & $python -m majesty_cam.cli poc-build `
        --game-path $GamePath `
        --input-root $InputRoot `
        --output-root $OutputRoot
    if ($LASTEXITCODE -ne 0) {
        throw "CAM Manager POC build failed with exit code $LASTEXITCODE"
    }
}
finally {
    $env:PYTHONPATH = $savedPythonPath
}
