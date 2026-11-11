$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$python=Join-Path $repo '.venv/Scripts/python.exe'
$output=Join-Path $repo 'dist/reward-factor-alpha'
$work=Join-Path $repo 'local/reward-contributions/unchanged-alpha'
$name='Majesty Mod Manager - Panel Engine Alpha'
$app=Join-Path $output $name
$payload=Join-Path $repo 'local/panel-engine-alpha/package-payload'
$env:PYTHONPATH=(Join-Path $repo 'src')+';'+(Join-Path $repo 'tests')+';'+(Join-Path $repo 'scripts')+';'+$env:PYTHONPATH
$env:QT_QPA_PLATFORM='offscreen'
$env:TEMP=Join-Path $repo 'local/panel-engine-alpha/test-temp'
$env:TMP=$env:TEMP
function Assert-Closed {
    $running=Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and $_.Path.StartsWith($app+'\',[StringComparison]::OrdinalIgnoreCase)
    }
    if($running){throw 'Close the reward-factor alpha candidate before replacing it.'}
}
function Protected-Files {
    $files=@{}
    $paths=@('dist/Majesty Mod Manager','dist/panel-engine-alpha','dist/release-candidate','dist/workshop-upload') |
        ForEach-Object { Join-Path $repo $_ }
    $paths+=@('MajestyModManager','MajestyModManagerPanelEngineAlpha') |
        ForEach-Object { Join-Path $env:LOCALAPPDATA $_ }
    $paths+=@('Majesty Mod Manager - Merged','Majesty Mod Manager - Panel Engine Alpha') |
        ForEach-Object { Join-Path ([Environment]::GetFolderPath('MyDocuments')) ('My Games/MajestyHD/Mods/'+$_) }
    foreach($path in $paths){
        if(Test-Path -LiteralPath $path){
            Get-ChildItem -LiteralPath $path -Recurse -File | ForEach-Object {
                $files[$_.FullName]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            }
        }
    }
    return $files
}
Assert-Closed
New-Item -ItemType Directory -Path $work -Force | Out-Null
$before=Protected-Files
$before | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'protected-before.json') -Encoding UTF8
$pins=Join-Path (Split-Path -Parent $repo) 'majesty-gold-hd-custom-guild-witch-hunter/private/manager-side-reward-adapter-20261110/alpha-inputs.json'
$inputs=Get-Content -LiteralPath $pins -Raw | ConvertFrom-Json
& $python (Join-Path $PSScriptRoot 'verify_reward_contribution_candidates.py') --infer --input-receipt $pins `
    --merge-root $inputs.records.witch_candidate.root --native-root $inputs.unchanged_alpha_candidate.root --work $work
if($LASTEXITCODE -ne 0){throw 'Unchanged-input composition/compiler proof failed.'}
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode panel-engine-alpha --receipt-root (Join-Path $work 'regression')
if($LASTEXITCODE -ne 0){throw 'Reward-factor alpha source regression failed.'}
Assert-Closed
$installer=Join-Path $work 'pyinstaller'
New-Item -ItemType Directory -Path $installer -Force | Out-Null
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name $name `
    --icon (Join-Path $repo 'src/majesty_cam/manager/assets/manager-icon.ico') `
    --distpath $output --workpath $installer --specpath $installer --paths (Join-Path $repo 'src') `
    --add-data ($payload+';payload') --add-data ((Join-Path $repo 'profiles')+';profiles') `
    --add-data ((Join-Path $repo 'src/majesty_cam/manager/theme.qss')+';majesty_cam/manager') `
    --add-data ((Join-Path $repo 'src/majesty_cam/manager/assets')+';majesty_cam/manager/assets') `
    (Join-Path $PSScriptRoot 'panel_engine_alpha_entry.py')
if($LASTEXITCODE -ne 0){throw 'Reward-factor alpha packaging failed.'}
foreach($file in @('LICENSE','THIRD-PARTY-NOTICES.md')){
    Copy-Item -LiteralPath (Join-Path $repo $file) -Destination $app -Force
}
Copy-Item -LiteralPath (Join-Path $repo 'licenses') -Destination $app -Recurse -Force
@'
REWARD FACTOR PANEL ENGINE ALPHA

This candidate uses the existing Panel Engine Alpha settings, private game EXE
and alpha output. It does not replace the working alpha app or beta app.
Prepare your alpha selection yourself before testing this new source composition.
Unchanged Standard scripts remain independently loaded. Only proven reward
factors combine; unsupported overlaps retain normal preferred-mod choices.
No native runtime or continuous diagnostic was added for this adapter.
In-game movement, save/load and payout acceptance still need player testing.
'@ | Set-Content -LiteralPath (Join-Path $app 'START HERE.txt') -Encoding UTF8
& $python (Join-Path $PSScriptRoot 'verify_alpha_cold_start.py') --application $app
if($LASTEXITCODE -ne 0){throw 'Reward-factor alpha packaged cold-start failed.'}
& $python (Join-Path $PSScriptRoot 'verify_regression.py') --mode panel-engine-alpha --application $app `
    --executable-name ($name+'.exe') --receipt-root (Join-Path $work 'regression')
if($LASTEXITCODE -ne 0){throw 'Reward-factor alpha packaged regression failed.'}
& $python (Join-Path $PSScriptRoot 'verify_packaged_reward_factors.py') --application $app --input-receipt $pins `
    --merge-root $inputs.records.witch_candidate.root --native-root $inputs.unchanged_alpha_candidate.root `
    --work (Join-Path $work 'packaged-language')
if($LASTEXITCODE -ne 0){throw 'Packaged unchanged-input composition/compiler proof failed.'}
$after=Protected-Files
if($after.Count -ne $before.Count){throw 'Protected file inventory changed during candidate packaging.'}
foreach($file in $before.Keys){if($after[$file] -ne $before[$file]){throw ('Protected file changed: '+$file)}}
$after | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'protected-after.json') -Encoding UTF8
Write-Output (Join-Path $app ($name+'.exe'))
