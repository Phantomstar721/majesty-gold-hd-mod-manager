param(
    [Parameter(Mandatory = $true)][string]$PublicExe,
    [Parameter(Mandatory = $true)][string]$Beta2Exe
)

$ErrorActionPreference = "Stop"
$runtimeSource = Get-Content (Join-Path $PSScriptRoot "..\runtime\MajestyModManagerRuntime.cpp") -Raw

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Pe([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    [byte[]]$bytes = [IO.File]::ReadAllBytes($resolved)
    $pe = [BitConverter]::ToInt32($bytes, 0x3C)
    Assert-True ([BitConverter]::ToUInt32($bytes, $pe) -eq 0x00004550) "Invalid PE: $resolved"
    $count = [BitConverter]::ToUInt16($bytes, $pe + 6)
    $timestamp = [BitConverter]::ToUInt32($bytes, $pe + 8)
    $optionalSize = [BitConverter]::ToUInt16($bytes, $pe + 20)
    $sectionBase = $pe + 24 + $optionalSize
    $sections = @()
    for ($index = 0; $index -lt $count; $index++) {
        $offset = $sectionBase + 40 * $index
        $sections += [pscustomobject]@{
            VirtualSize = [BitConverter]::ToUInt32($bytes, $offset + 8)
            Rva = [BitConverter]::ToUInt32($bytes, $offset + 12)
            RawSize = [BitConverter]::ToUInt32($bytes, $offset + 16)
            RawOffset = [BitConverter]::ToUInt32($bytes, $offset + 20)
        }
    }
    [pscustomobject]@{
        Path = $resolved
        Bytes = $bytes
        Timestamp = $timestamp
        Version = (Get-Item -LiteralPath $resolved).VersionInfo.FileVersion
        Sections = $sections
    }
}

function Get-RvaOffset($Pe, [uint32]$Rva) {
    foreach ($section in $Pe.Sections) {
        $span = [Math]::Max($section.VirtualSize, $section.RawSize)
        if ($Rva -ge $section.Rva -and $Rva -lt ($section.Rva + $span)) {
            return [int]($section.RawOffset + $Rva - $section.Rva)
        }
    }
    throw ("RVA 0x{0:X8} is not mapped in {1}." -f $Rva, $Pe.Path)
}

function Read-RvaBytes($Pe, [uint32]$Rva, [int]$Count) {
    $offset = Get-RvaOffset $Pe $Rva
    [byte[]]$result = New-Object byte[] $Count
    [Array]::Copy($Pe.Bytes, $offset, $result, 0, $Count)
    return $result
}

function Assert-Bytes($Pe, [uint32]$Rva, [string]$Hex, [string]$Label) {
    [byte[]]$expected = [Convert]::FromHexString($Hex)
    [byte[]]$actual = Read-RvaBytes $Pe $Rva $expected.Length
    Assert-True (
        [Convert]::ToHexString($actual) -eq [Convert]::ToHexString($expected)
    ) ("{0} differs at RVA 0x{1:X8} in {2}." -f $Label, $Rva, $Pe.Path)
}

function Assert-CallTarget($Pe, [uint32]$CallRva, [uint32]$TargetRva, [string]$Label) {
    [byte[]]$call = Read-RvaBytes $Pe $CallRva 5
    Assert-True ($call[0] -eq 0xE8) ("$Label is not a relative call in $($Pe.Path).")
    $relative = [BitConverter]::ToInt32($call, 1)
    $actualTarget = [uint32]([int64]$CallRva + 5 + $relative)
    Assert-True ($actualTarget -eq $TargetRva) (
        "{0} targets RVA 0x{1:X8}, expected 0x{2:X8}, in {3}." -f
        $Label, $actualTarget, $TargetRva, $Pe.Path)
}

$profiles = @(
    [pscustomobject]@{
        Id = "public-1.5.2.24"
        Version = "1.5.2.24"
        Timestamp = [uint32]0x5897B72F
        Path = $PublicExe
        Resolver = [uint32]0x00108480
        EntryHex = "56E86A6A0500"
        Provider = [uint32]0x0015EEF0
        StringAssign = [uint32]0x00228350
        AssignCall = [uint32]0x001084A6
        LocalChatCall = [uint32]0x0002DF5B
        MessageFlagPresenterCall = [uint32]0x0005BE96
        HeroPanelCall = [uint32]0x0009875B
    },
    [pscustomobject]@{
        Id = "beta2-1.5.2.28"
        Version = "1.5.2.28"
        Timestamp = [uint32]0x5A8A11D5
        Path = $Beta2Exe
        Resolver = [uint32]0x0010A650
        EntryHex = "56E8DAA90600"
        Provider = [uint32]0x00175030
        StringAssign = [uint32]0x0023AAF0
        AssignCall = [uint32]0x0010A676
        LocalChatCall = [uint32]0x0002EEBB
        MessageFlagPresenterCall = [uint32]0x0005CEC6
        HeroPanelCall = [uint32]0x00098D8B
    }
)

foreach ($profile in $profiles) {
    $pe = Read-Pe $profile.Path
    Assert-True ($pe.Version -eq $profile.Version) "Wrong version for $($profile.Id)."
    Assert-True ($pe.Timestamp -eq $profile.Timestamp) "Wrong timestamp for $($profile.Id)."
    Assert-Bytes $pe $profile.Resolver $profile.EntryHex "shared resolver entry"
    Assert-CallTarget $pe ($profile.Resolver + 1) $profile.Provider "resolver table-provider call"
    Assert-CallTarget $pe $profile.AssignCall $profile.StringAssign "resolver stock string assignment"
    Assert-CallTarget $pe $profile.LocalChatCall $profile.Resolver "LocalChatMessage resolution"
    Assert-CallTarget $pe $profile.MessageFlagPresenterCall $profile.Resolver "MessageFlag presenter resolution"
    Assert-CallTarget $pe $profile.HeroPanelCall $profile.Resolver "hero-panel intent resolution"
    Assert-True ($runtimeSource.Contains(('0x{0:X8}' -f $profile.Resolver))) (
        "Runtime omits the $($profile.Id) resolver RVA.")
    Assert-True ($runtimeSource.Contains(('0x{0:X8}' -f $profile.Provider))) (
        "Runtime omits the $($profile.Id) table-provider RVA.")
}

Write-Host "Validated the shared activity-text lifecycle for public and beta2 runtime profiles."
