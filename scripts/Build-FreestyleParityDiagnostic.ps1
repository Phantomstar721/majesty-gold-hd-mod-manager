param(
    [string]$OutputRoot = ".\artifacts\runtime-freestyle-parity-test"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $PSScriptRoot "Build-Runtime.ps1"
$output = if ([IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot
} else {
    Join-Path $repoRoot $OutputRoot
}

& $buildScript -OutputRoot $output -FreestyleDiagnosticParity
if ($LASTEXITCODE -ne 0) {
    throw "Freestyle parity diagnostic build failed with exit code $LASTEXITCODE"
}

$log = Join-Path $output "MajestyBuildingRuntime.log"
if (Test-Path -LiteralPath $log -PathType Leaf) {
    Remove-Item -LiteralPath $log -Force
}

Write-Host "Prepared isolated Freestyle parity diagnostic runtime:"
Write-Host $output
