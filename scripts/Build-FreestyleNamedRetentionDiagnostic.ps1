param(
    [string]$OutputRoot = ".\artifacts\runtime-freestyle-named-retention-test"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildScript = Join-Path $PSScriptRoot "Build-Runtime.ps1"
$output = if ([IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot
} else {
    Join-Path $repoRoot $OutputRoot
}

& $buildScript -OutputRoot $output -FreestyleDiagnosticNamedRetention
if ($LASTEXITCODE -ne 0) {
    throw "Freestyle named-retention diagnostic build failed with exit code $LASTEXITCODE"
}

$log = Join-Path $output "MajestyBuildingRuntime.log"
if (Test-Path -LiteralPath $log -PathType Leaf) {
    Remove-Item -LiteralPath $log -Force
}

Write-Host "Prepared isolated Freestyle named-retention diagnostic runtime:"
Write-Host $output
