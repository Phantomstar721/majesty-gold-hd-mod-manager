param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string]$DataRoot
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path $repo ('local\gog-qol-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$helpers = @('downloadable-quests-shortcut','quest-map-drag','unlock-all-quests',
    'suppress-all-message-flags','remember-game-speed','remember-camera-zoom',
    'lower-tracking-window','remember-active-mods','generic-visitor-lists')
$expectedExe = (Get-FileHash -LiteralPath $Executable).Hash
$ui = @(Get-ChildItem -LiteralPath $DataRoot -Filter 'UIData_*.dat' -File)
if ($ui.Count -eq 0) { throw 'No reference UI layouts found.' }
$expectedUi = @{}
foreach ($file in $ui) { $expectedUi[$file.Name] = (Get-FileHash -LiteralPath $file.FullName).Hash }

function Invoke-Helper {
    param([string]$Slug,[string]$Game,[switch]$Restore,[switch]$DryRun)
    $verb = if ($Restore) { 'Restore' } else { 'Install' }
    $script = @(Get-ChildItem (Join-Path $repo ('helpers\'+$Slug+'\scripts')) -Filter ($verb+'-*.ps1'))
    if ($script.Count -ne 1) { throw "Missing or ambiguous $verb script: $Slug" }
    $arguments = @{ GamePath=$Game }
    if ($DryRun) { $arguments.DryRun=$true }
    if (-not $Restore -and $Slug -in @('remember-game-speed','remember-camera-zoom','remember-active-mods')) {
        $arguments.PreferenceDirectory=Join-Path $Game 'prefs'
    }
    $log = Join-Path $Game ($Slug+'-'+$verb+'-'+$DryRun+'.log')
    try { & $script[0].FullName @arguments *> $log }
    catch { throw "$Slug $verb failed: $($_.Exception.Message). Details: $log" }
}

foreach ($order in 0,1) {
    $game = Join-Path $work "order-$order"
    New-Item -ItemType Directory -Path (Join-Path $game 'Data') | Out-Null
    $exe = Join-Path $game 'MajestyHD.exe'
    Copy-Item -LiteralPath $Executable -Destination $exe
    foreach ($file in $ui) { Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $game 'Data') }
    $sequence = @($helpers)
    if ($order -eq 1) { [Array]::Reverse($sequence) }
    foreach ($slug in $sequence) { Invoke-Helper $slug $game }
    $installedHash = (Get-FileHash -LiteralPath $exe).Hash
    foreach ($slug in $sequence) { Invoke-Helper $slug $game -DryRun }
    if ((Get-FileHash -LiteralPath $exe).Hash -ne $installedHash) { throw 'Dry-run changed the executable.' }
    # Every installed script must be idempotent with all other helpers present.
    foreach ($slug in $sequence) { Invoke-Helper $slug $game }
    if ((Get-FileHash -LiteralPath $exe).Hash -ne $installedHash) { throw 'Repeated install changed the executable.' }
    Copy-Item -LiteralPath $exe -Destination (Join-Path $work "all-installed-$order.exe")
    [Array]::Reverse($sequence)
    foreach ($slug in $sequence) { Invoke-Helper $slug $game -Restore }
    if ((Get-FileHash -LiteralPath $exe).Hash -ne $expectedExe) { throw "Executable roundtrip differs in order $order." }
    foreach ($name in $expectedUi.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $game ('Data\'+$name))).Hash -ne $expectedUi[$name]) { throw "UI roundtrip differs: $name, order $order." }
    }
}

# Removing an earlier private section leaves it inert until it is last; a
# later helper must keep its original RVA and remain independently reversible.
$game = Join-Path $work 'order-0'
Invoke-Helper 'unlock-all-quests' $game
Invoke-Helper 'remember-camera-zoom' $game
Invoke-Helper 'unlock-all-quests' $game -Restore
Invoke-Helper 'remember-camera-zoom' $game -DryRun
Invoke-Helper 'unlock-all-quests' $game
Invoke-Helper 'remember-camera-zoom' $game -Restore
Invoke-Helper 'unlock-all-quests' $game -Restore
if ((Get-FileHash (Join-Path $game 'MajestyHD.exe')).Hash -ne $expectedExe) { throw 'Inert-section reuse did not roundtrip.' }

# Reject a changed stock callee before either the executable or UI is touched.
$exe = Join-Path $game 'MajestyHD.exe'
[byte[]]$bytes = [IO.File]::ReadAllBytes($exe)
$bytes[0x1F13A8] = $bytes[0x1F13A8] -bxor 1
[IO.File]::WriteAllBytes($exe,$bytes)
$before = (Get-FileHash $exe).Hash
$rejected = $false
try { Invoke-Helper 'remember-camera-zoom' $game } catch {
    if ($_.Exception.Message -notlike '*stock QoL lifecycle bytes differ*') { throw }
    $rejected=$true
}
if (-not $rejected -or (Get-FileHash $exe).Hash -ne $before) { throw 'Changed stock zoom code was not rejected without mutation.' }
# Retain fixtures for native profile checks; no game or Manager process runs.
Write-Output $work
