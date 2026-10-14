param(
    [ValidateSet("release", "development")][string]$Mode = "",
    [string]$ApplicationRoot = "",
    [string]$GameRoot = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $Mode) { $Mode = (Get-Content -LiteralPath (Join-Path $repo 'regression-mode.txt') -Raw).Trim() }
$configured = (Get-Content -LiteralPath (Join-Path $repo 'regression-mode.txt') -Raw).Trim()
if ($Mode -ne $configured) { throw "Wrong checkout for $Mode; this checkout is $configured." }
$python = Join-Path $repo '.venv\Scripts\python.exe'
$fixtures = Join-Path (Split-Path -Parent $repo) 'majesty-gold-hd-mod-manager-gog-support\local\fixtures'
# Caller-supplied fixture paths take precedence. No game or Windows settings change.
if (-not $env:MAJESTY_PUBLIC_EXE) { $env:MAJESTY_PUBLIC_EXE = Join-Path $GameRoot 'MajestyHD.exe' }
if (-not $env:MAJESTY_BETA2_EXE) { $env:MAJESTY_BETA2_EXE = Join-Path $fixtures 'beta2\MajestyHD.exe' }
if (-not $env:MAJESTY_GOG_EXE) { $env:MAJESTY_GOG_EXE = Join-Path $fixtures 'gog-pristine\MajestyHD.exe' }
$env:MAJESTY_STOCK_ROOT = $GameRoot
if (-not $ApplicationRoot) { $ApplicationRoot = Join-Path $repo 'dist\Majesty Mod Manager' }
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode $Mode
if ($LASTEXITCODE -ne 0) { throw 'Source regression gate failed.' }
if ($Mode -eq 'release') {
    & $python (Join-Path $PSScriptRoot 'verify_release_parity.py')
    if ($LASTEXITCODE -ne 0) { throw 'Release package/three-version gate failed.' }
}
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode $Mode --application $ApplicationRoot
if ($LASTEXITCODE -ne 0) { throw 'Packaged regression gate failed.' }
