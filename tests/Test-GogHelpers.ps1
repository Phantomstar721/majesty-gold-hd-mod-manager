param([Parameter(Mandatory = $true)][string[]]$Executable)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$scratch = Join-Path $repoRoot ("local\helper-roundtrip-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $scratch | Out-Null
$helpers = @(
    @{ Root="remember-active-mods"; Install="Install-ModPersistence.ps1"; Restore="Restore-ModPersistence.ps1" },
    @{ Root="generic-visitor-lists"; Install="Install-GenericVisitorLists.ps1"; Restore="Restore-GenericVisitorLists.ps1" }
)

function Run-Helper($helper, [string]$operation, [string]$game, [switch]$DryRun) {
    $arguments = @{ GamePath = $game }
    if ($DryRun) { $arguments.DryRun = $true }
    if ($operation -eq "Install" -and $helper.Root -eq "remember-active-mods") {
        $arguments.PreferenceDirectory = Join-Path $scratch "preferences"
    }
    $script = Join-Path $repoRoot ("helpers\" + $helper.Root + "\scripts\" + $helper[$operation])
    & $script @arguments *> (Join-Path $scratch "last-operation.log")
}

foreach ($source in $Executable) {
    $before = (Get-FileHash -LiteralPath $source).Hash
    foreach ($order in @(@(0,1), @(1,0))) {
        $game = Join-Path $scratch ([guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $game | Out-Null
        $copy = Join-Path $game "MajestyHD.exe"
        Copy-Item -LiteralPath $source -Destination $copy
        foreach ($index in $order) {
            Run-Helper $helpers[$index] "Install" $game -DryRun
            Run-Helper $helpers[$index] "Install" $game
            $installed = (Get-FileHash -LiteralPath $copy).Hash
            Run-Helper $helpers[$index] "Install" $game
            if ((Get-FileHash -LiteralPath $copy).Hash -ne $installed) { throw "Helper is not idempotent" }
        }
        # Remove the earlier section first, exercising inert-section ownership.
        foreach ($index in $order) { Run-Helper $helpers[$index] "Restore" $game }
        foreach ($index in $order) { Run-Helper $helpers[$index] "Restore" $game }
        if ((Get-FileHash -LiteralPath $copy).Hash -ne $before) { throw "Helper round trip did not restore exact input bytes" }
    }
    if ((Get-FileHash -LiteralPath $source).Hash -ne $before) { throw "Source fixture changed" }
}
# Retain the isolated fixtures and last operation log for diagnosis. Never touch
# installed game files, Documents mods, or a Manager-generated package.
