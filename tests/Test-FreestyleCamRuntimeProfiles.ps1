param(
    [Parameter(Mandatory = $true)][string]$PublicExe,
    [Parameter(Mandatory = $true)][string]$Beta2Exe
)

$ErrorActionPreference = "Stop"

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Pe([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    [byte[]]$bytes = [IO.File]::ReadAllBytes($resolved)
    $pe = [BitConverter]::ToInt32($bytes, 0x3C)
    Assert-True ([BitConverter]::ToUInt32($bytes, $pe) -eq 0x00004550) "Invalid PE: $resolved"
    $sectionCount = [BitConverter]::ToUInt16($bytes, $pe + 6)
    $optionalSize = [BitConverter]::ToUInt16($bytes, $pe + 20)
    $sectionTable = $pe + 24 + $optionalSize
    $sections = @()
    for ($index = 0; $index -lt $sectionCount; $index++) {
        $offset = $sectionTable + 40 * $index
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
        Timestamp = [BitConverter]::ToUInt32($bytes, $pe + 8)
        Version = (Get-Item -LiteralPath $resolved).VersionInfo.FileVersion
        Sections = $sections
    }
}

function Read-RvaBytes($Pe, [uint32]$Rva, [int]$Count) {
    foreach ($section in $Pe.Sections) {
        $span = [Math]::Max($section.VirtualSize, $section.RawSize)
        if ($Rva -ge $section.Rva -and $Rva -lt ($section.Rva + $span)) {
            $offset = [int]($section.RawOffset + $Rva - $section.Rva)
            [byte[]]$result = New-Object byte[] $Count
            [Array]::Copy($Pe.Bytes, $offset, $result, 0, $Count)
            return $result
        }
    }
    throw ("Unmapped RVA 0x{0:X8} in {1}" -f $Rva, $Pe.Path)
}

function Assert-Pattern($Pe, [string]$Name, [uint32]$Rva, [string]$Hex) {
    [byte[]]$expected = [Convert]::FromHexString($Hex)
    [byte[]]$actual = Read-RvaBytes $Pe $Rva $expected.Length
    Assert-True (
        [Convert]::ToHexString($actual) -eq [Convert]::ToHexString($expected)
    ) ("{0} differs at RVA 0x{1:X8} in {2}" -f $Name, $Rva, $Pe.Path)
}

$common = @(
    @{ Name="handle use"; Public=0x00271FD0; Beta2=0x00287430; Hex="8BC18B482C85C97444" },
    @{ Name="named handle use"; Public=0x00272030; Beta2=0x00287490; Hex="53568B712C32DB85F6747B" },
    @{ Name="frame walk"; Public=0x002728C0; Beta2=0x00287D20; Hex="53568BF1BB01000000845E68" },
    @{ Name="grid draw"; Public=0x00272450; Beta2=0x002878B0; Hex="83EC4C5355568B74245C" },
    @{ Name="grid prescan"; Public=0x0027258C; Beta2=0x002879EC; Hex="8B7D2C8B4C2464518BCF" },
    @{ Name="cache getter"; Public=0x0025C810; Beta2=0x00271C70; Hex="568BF18B863801000085C07543" },
    @{ Name="owner destructor"; Public=0x0026F1E1; Beta2=0x00284641; Hex="8B4E28C70600000000C746040000000085C97407" },
    @{ Name="wrapper assignment"; Public=0x0026C740; Beta2=0x00281BA0; Hex="56578B7C240C8B078B108BF1" },
    @{ Name="release thunk"; Public=0x00246950; Beta2=0x0025BDB0; Hex="8B4C24048B018B5004FFE2" },
    @{ Name="vtable8 release one"; Public=0x002BDF0A; Beta2=0x002D349A; Hex="8B018B5008FFD2" },
    @{ Name="vtable8 release two"; Public=0x002BDF2A; Beta2=0x002D34BA; Hex="8B018B5008FFD2" }
)

$public = Read-Pe $PublicExe
$beta2 = Read-Pe $Beta2Exe
Assert-True ($public.Timestamp -eq 0x5897B72F -and $public.Version -eq "1.5.2.24") "Public fixture is not 1.5.2.24"
Assert-True ($beta2.Timestamp -eq 0x5A8A11D5 -and $beta2.Version -eq "1.5.2.28") "beta2 fixture is not 1.5.2.28"
foreach ($pattern in $common) {
    Assert-Pattern $public $pattern.Name $pattern.Public $pattern.Hex
    Assert-Pattern $beta2 $pattern.Name $pattern.Beta2 $pattern.Hex
}
Assert-Pattern $public "manager singleton" 0x00226AC1 "A118887C0085C0"
Assert-Pattern $beta2 "manager singleton" 0x00246641 "A118757E0085C0"

$source = Get-Content -Raw (Join-Path $PSScriptRoot "..\runtime\FreestyleCamRuntime.cpp")
foreach ($required in @(
    '"public-1.5.2.24"',
    '"beta2-1.5.2.28"',
    "PreflightProfile()",
    "RollBackPatches()",
    "kImageResourceType",
    "push 047414D49h",
    "g_profile->managerSingletonRva",
    "WriteReleaseVtable8Patch",
    "installed stock IMAG rebind and dead-wrapper teardown guards"
)) {
    Assert-True ($source.Contains($required)) "Freestyle runtime contract missing: $required"
}

Write-Host "Validated Freestyle CAM runtime sites for public and beta2 profiles."
