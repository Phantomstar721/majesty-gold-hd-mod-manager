param(
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD",
    [string]$RuntimeRoot = ".\artifacts\runtime",
    [string[]]$GameArguments = @()
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = if ([IO.Path]::IsPathRooted($RuntimeRoot)) {
    $RuntimeRoot
} else {
    Join-Path $repoRoot $RuntimeRoot
}
$launcher = Join-Path $runtime "MajestyBuildingRuntimeLauncher.exe"
$dll = Join-Path $runtime "MajestyBuildingRuntime.dll"
$game = Join-Path $GamePath "MajestyHD.exe"
foreach ($path in @($launcher, $dll, $game)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required runtime file was not found: $path"
    }
}

if (Get-Process -Name "MajestyHD" -ErrorAction SilentlyContinue) {
    throw "MajestyHD.exe is already running. Fully close it before launching the injected runtime."
}

& $launcher $game $dll @GameArguments
if ($LASTEXITCODE -ne 0) {
    throw "Runtime launcher failed with exit code $LASTEXITCODE"
}
