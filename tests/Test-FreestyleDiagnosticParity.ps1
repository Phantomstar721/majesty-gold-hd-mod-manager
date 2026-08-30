$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeSourcePath = Join-Path $repoRoot "runtime\FreestyleCamRuntime.cpp"
$buildScript = Join-Path $repoRoot "scripts\Build-FreestyleParityDiagnostic.ps1"
$output = Join-Path $repoRoot "artifacts\runtime-freestyle-parity-test"
$namedBuildScript = Join-Path $repoRoot "scripts\Build-FreestyleNamedRetentionDiagnostic.ps1"
$namedOutput = Join-Path $repoRoot "artifacts\runtime-freestyle-named-retention-test"
$source = Get-Content -LiteralPath $runtimeSourcePath -Raw

foreach ($contract in @(
    "FREESTYLE_CAM_DIAGNOSTIC_PARITY",
    "g_diagnosticTracing",
    "g_namedRetentionOnly",
    "namedWrapperCopyCallerRva",
    "0x002D23DA",
    "parityRetention",
    "diag acquire",
    "diag stale",
    "diag invalidate",
    "diag assign",
    "upstream-parity-diagnostic"
)) {
    if (-not $source.Contains($contract)) {
        throw "Freestyle diagnostic parity contract is missing: $contract"
    }
}

& $buildScript -OutputRoot $output
if ($LASTEXITCODE -ne 0) {
    throw "Freestyle diagnostic parity build failed with exit code $LASTEXITCODE"
}

$dll = Join-Path $output "MajestyBuildingRuntime.dll"
$launcher = Join-Path $output "MajestyBuildingRuntimeLauncher.exe"
foreach ($path in @($dll, $launcher)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Diagnostic runtime artifact is missing: $path"
    }
}

$dllText = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($dll))
if (-not $dllText.Contains("upstream-parity-diagnostic")) {
    throw "Diagnostic runtime DLL does not contain its parity mode label."
}

& $namedBuildScript -OutputRoot $namedOutput
if ($LASTEXITCODE -ne 0) {
    throw "Freestyle named-retention diagnostic build failed with exit code $LASTEXITCODE"
}
$namedDll = Join-Path $namedOutput "MajestyBuildingRuntime.dll"
$namedLauncher = Join-Path $namedOutput "MajestyBuildingRuntimeLauncher.exe"
foreach ($path in @($namedDll, $namedLauncher)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Named-retention diagnostic artifact is missing: $path"
    }
}
$namedDllText = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($namedDll))
if (-not $namedDllText.Contains("named-wrapper-retention-diagnostic")) {
    throw "Named-retention runtime DLL does not contain its mode label."
}

Write-Host "Freestyle parity diagnostic runtime tests passed."
