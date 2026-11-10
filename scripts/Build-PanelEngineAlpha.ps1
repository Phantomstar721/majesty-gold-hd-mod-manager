param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv/Scripts/python.exe'
$output = [IO.Path]::GetFullPath((Join-Path $repo 'dist/panel-engine-alpha'))
$work = [IO.Path]::GetFullPath((Join-Path $repo 'local/panel-engine-alpha/pyinstaller'))
$receipts = Join-Path $repo 'local/panel-engine-alpha/regression'
$name = 'Majesty Mod Manager - Panel Engine Alpha'
$application = Join-Path $output $name
$boundary = [IO.Path]::GetFullPath($repo).TrimEnd('\') + '\'
if (-not $output.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase) -or
    -not $work.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Alpha output escapes repository.' }
$locked = Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($application, [StringComparison]::OrdinalIgnoreCase)
}
if ($locked) { throw 'Close the panel engine alpha before replacing it.' }
function ProtectedApplicationHashes {
    $result = @{}
    foreach ($folder in @('dist/Majesty Mod Manager','dist/release-candidate','dist/workshop-upload')) {
        $path = Join-Path $repo $folder
        if (Test-Path -LiteralPath $path) {
            Get-ChildItem -LiteralPath $path -Recurse -File -Force | Where-Object { $_.Extension -ne '.log' } | ForEach-Object {
                $result[$_.FullName] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
    }
    return $result
}
$protected = ProtectedApplicationHashes
$env:PYTHONPATH=(Join-Path $repo 'src')+';'+$env:PYTHONPATH
$env:QT_QPA_PLATFORM='offscreen'
$tempRoot=Join-Path $repo 'local/panel-engine-alpha/test-temp'
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$env:TEMP=$tempRoot
$env:TMP=$tempRoot
& $python (Join-Path $PSScriptRoot 'build_panel_engine_modules.py')
if ($LASTEXITCODE -ne 0) { throw 'Native alpha module build failed.' }
& $python (Join-Path $PSScriptRoot 'prepare_panel_engine_descriptor_fixtures.py')
if ($LASTEXITCODE -ne 0) { throw 'Native alpha descriptor preparation failed.' }
& (Join-Path $PSScriptRoot 'Build-Runtime.ps1') -PanelEngineAlpha -FeatureTests -OutputRoot 'local/panel-engine-alpha/runtime'
if ($LASTEXITCODE -ne 0) { throw 'Native alpha runtime build failed.' }
$alphaPayload=Join-Path $repo 'local/panel-engine-alpha/package-payload'
New-Item -ItemType Directory -Path $alphaPayload -Force | Out-Null
Copy-Item -Path (Join-Path $repo 'payload/*') -Destination $alphaPayload -Recurse -Force
$nativePayload=Join-Path $alphaPayload 'panel-engine'
$modulesPayload=Join-Path $nativePayload 'modules'
$runtimePayload=Join-Path $nativePayload 'runtime'
New-Item -ItemType Directory -Path $modulesPayload,$runtimePayload -Force | Out-Null
foreach ($file in @('MajestyBuildingRuntime.dll','MajestyBuildingRuntimeLauncher.exe')) {
    Copy-Item -LiteralPath (Join-Path $repo ('local/panel-engine-alpha/runtime/'+$file)) -Destination $runtimePayload -Force
}
foreach ($file in @('modules.json','window-engine-public.mmne','window-engine-beta2.mmne','window-engine-gog.mmne',
                    'script-functions-public.mmne','script-functions-beta2.mmne','script-functions-gog.mmne')) {
    Copy-Item -LiteralPath (Join-Path $repo ('local/panel-engine-alpha/native-modules/'+$file)) -Destination $modulesPayload -Force
}
& $python (Join-Path $PSScriptRoot 'verify_alpha_cold_start.py')
if ($LASTEXITCODE -ne 0) { throw 'Alpha cold-start source check failed.' }
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode panel-engine-alpha --receipt-root $receipts
if ($LASTEXITCODE -ne 0) { throw 'Alpha source regression gate failed.' }
New-Item -ItemType Directory -Path $work -Force | Out-Null
# All alpha native payloads are separate from beta and Workshop build inputs.
& $python -m PyInstaller --noconfirm --clean --windowed --name $name `
    --icon (Join-Path $repo 'src/majesty_cam/manager/assets/manager-icon.ico') `
    --distpath $output --workpath $work --specpath $work --paths (Join-Path $repo 'src') `
    --add-data ($alphaPayload + ';payload') `
    --add-data ((Join-Path $repo 'profiles') + ';profiles') `
    --add-data ((Join-Path $repo 'src/majesty_cam/manager/theme.qss') + ';majesty_cam/manager') `
    --add-data ((Join-Path $repo 'src/majesty_cam/manager/assets') + ';majesty_cam/manager/assets') `
    (Join-Path $PSScriptRoot 'panel_engine_alpha_entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Alpha packaging failed.' }
foreach ($file in @('LICENSE','THIRD-PARTY-NOTICES.md')) {
    Copy-Item -LiteralPath (Join-Path $repo $file) -Destination $application -Force
}
Copy-Item -LiteralPath (Join-Path $repo 'licenses') -Destination $application -Recurse -Force
@'
PANEL ENGINE ALPHA

This alpha has separate Manager settings and profile output. It does not replace the beta Manager.
Choose your game installation, then install Custom Building Panels and/or Scripted Ground Actions
from Quality of Life when your selected mods require them. These are independent optional patches.
The alpha runs MajestyHD.PanelEngineAlpha.exe beside your original game executable.
Use Classic Launch for ordinary engine mods. Prepare any Merge selections yourself in the alpha.
Repeat the same checks on Default Steam, beta2 and GOG; native game acceptance is still pending.
'@ | Set-Content -LiteralPath (Join-Path $application 'START HERE.txt') -Encoding utf8
& $python (Join-Path $PSScriptRoot 'verify_alpha_cold_start.py') --application $application
if ($LASTEXITCODE -ne 0) { throw 'Packaged alpha cold-start check failed.' }
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode panel-engine-alpha --application $application --executable-name ($name+'.exe') --receipt-root $receipts
if ($LASTEXITCODE -ne 0) { throw 'Packaged alpha regression gate failed.' }
$after = ProtectedApplicationHashes
if ($after.Count -ne $protected.Count) { throw 'Protected application contents changed during the alpha build.' }
foreach ($file in $protected.Keys) {
    if ($after[$file] -ne $protected[$file]) { throw "Protected application changed: $file" }
}
Write-Output (Join-Path $application ($name+'.exe'))
