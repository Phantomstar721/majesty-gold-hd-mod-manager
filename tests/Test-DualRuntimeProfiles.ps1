param(
    [Parameter(Mandatory = $true)][string]$PublicExe,
    [Parameter(Mandatory = $true)][string]$Beta2Exe,
    [string]$PatchedBeta2Exe,
    [switch]$AllowModifiedReferences
)

$ErrorActionPreference = "Stop"
$runtimeSource = Get-Content (Join-Path $PSScriptRoot "..\runtime\MajestyModManagerRuntime.cpp") -Raw

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Pe([string]$Path) {
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    [byte[]]$bytes = [IO.File]::ReadAllBytes($resolved)
    Assert-True ($bytes.Length -ge 0x100) "Executable is too short: $resolved"
    $pe = [BitConverter]::ToInt32($bytes, 0x3C)
    Assert-True ([BitConverter]::ToUInt32($bytes, $pe) -eq 0x00004550) "Invalid PE signature: $resolved"
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
        Sections = $sections
        Sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
        FileVersion = (Get-Item -LiteralPath $resolved).VersionInfo.FileVersion
    }
}

function Read-RvaBytes($Pe, [uint32]$Rva, [int]$Count) {
    foreach ($section in $Pe.Sections) {
        $span = [Math]::Max($section.VirtualSize, $section.RawSize)
        if ($Rva -ge $section.Rva -and $Rva -lt ($section.Rva + $span)) {
            $fileOffset = [int]($section.RawOffset + $Rva - $section.Rva)
            [byte[]]$result = New-Object byte[] $Count
            [Array]::Copy($Pe.Bytes, $fileOffset, $result, 0, $Count)
            return $result
        }
    }
    throw ("RVA 0x{0:X8} is not mapped in {1}." -f $Rva, $Pe.Path)
}

function Assert-Pattern($Pe, $Pattern) {
    [byte[]]$expected = [Convert]::FromHexString($Pattern.Hex)
    [byte[]]$actual = Read-RvaBytes $Pe $Pattern.Rva $expected.Length
    Assert-True (
        [Convert]::ToHexString($actual) -eq [Convert]::ToHexString($expected)
    ) ("{0} differs at RVA 0x{1:X8} in {2}." -f $Pattern.Name, $Pattern.Rva, $Pe.Path)
}

$profiles = @(
    [pscustomobject]@{
        Id = "public-1.5.2.24"
        Version = "1.5.2.24"
        Timestamp = [uint32]0x5897B72F
        Sha256 = "AA9BE61DC095773CCC5C08B9E5729A30EE856258249371C5189CE52FB675DB00"
        Path = $PublicExe
        Patterns = @(
            @{ Name="secondary controller"; Rva=0x0002594A; Hex="8B6B2483C310" },
            @{ Name="dialog creation"; Rva=0x00025910; Hex="83EC0853555657" },
            @{ Name="dialog factory"; Rva=0x0010AC00; Hex="6AFF68170E7000" },
            @{ Name="AP08 constructor"; Rva=0x0009E1E0; Hex="6AFF68F8196F00" },
            @{ Name="AP08 vtable start"; Rva=0x0033D37C; Hex="A0E24900D0E54900406A490060E64900" },
            @{ Name="AP08 vtable boundary"; Rva=0x0033D3AC; Hex="C05249002367616D" },
            @{ Name="MX05 GPL scalar evaluator"; Rva=0x000BBDB0; Hex="6AFF68E0576F00" },
            @{ Name="MX05 post-submit control handoff"; Rva=0x000BC157; Hex="558BCEE811C0FDFF5F" },
            @{ Name="MX05 general control handoff"; Rva=0x000BC16E; Hex="558BCEE8FABFFDFF5F" },
            @{ Name="MX05 row-click focus branch"; Rva=0x000981A9; Hex="8B4E248B018B50686A006A00" },
            @{ Name="MX05 post-action focus branch"; Rva=0x000981E8; Hex="8B178B82B80000008BCFFFD0" },
            @{ Name="GPL integer argument adapter"; Rva=0x00162C60; Hex="83C108E9" },
            @{ Name="GPL result vector access"; Rva=0x0002DDF0; Hex="83EC08558B2D" },
            @{ Name="GPL agent result resolver"; Rva=0x00158B20; Hex="568BF18B4608" },
            @{ Name="MX05 row name call"; Rva=0x00098485; Hex="E8669EFAFF" },
            @{ Name="MX05 row intent call"; Rva=0x0009873D; Hex="E88E181200" },
            @{ Name="unknown dialog fallback"; Rva=0x0010C03F; Hex="8B4C240464890D000000005983C40CC21000CCCCCCCCCCCCCCCCCCCCCCCC" },
            @{ Name="shared guild allocation"; Rva=0x0010BE9C; Hex="6A34E8DBD01C00" },
            @{ Name="UI manager"; Rva=0x00025D00; Hex="6AFF68DB046E0064A100" },
            @{ Name="dialog removal"; Rva=0x00025880; Hex="83EC08535556578B7C24" },
            @{ Name="panel context"; Rva=0x00067540; Hex="8B512C33C085D274098B" },
            @{ Name="command metadata"; Rva=0x001C2060; Hex="83EC0C8D042450E894FE" },
            @{ Name="player agent"; Rva=0x00029580; Hex="A14C547C008B48048B11" },
            @{ Name="packed attribute"; Rva=0x001B9FD0; Hex="8B5424048D4424045052" },
            @{ Name="building command"; Rva=0x000C4CF0; Hex="6AFF68CB6F6F0064A100" },
            @{ Name="Rage dispatch"; Rva=0x000C4FE1; Hex="8B4D0C518BCF" },
            @{ Name="Rage branch"; Rva=0x000B1269; Hex="6841450000" },
            @{ Name="Rage GPL continuation"; Rva=0x000B12C9; Hex="8D4C2410E8AE671700C7" },
            @{ Name="game update call"; Rva=0x0002526D; Hex="E8DE130000" },
            @{ Name="game update"; Rva=0x00026650; Hex="83EC38568D442424508B" },
            @{ Name="stream control"; Rva=0x002524C0; Hex="53558BE98B4544837818" },
            @{ Name="research rows"; Rva=0x000A8AE0; Hex="558B6C2408578B7D04" },
            @{ Name="research row"; Rva=0x000A8870; Hex="6AFF68382F6F00" },
            @{ Name="research validation"; Rva=0x000A8B40; Hex="8B44240453565750" },
            @{ Name="research command"; Rva=0x000C2C60; Hex="6AFF681B696F00" },
            @{ Name="research completion"; Rva=0x000DFE20; Hex="6AFF68A0AD6F00" },
            @{ Name="research completion dispatch"; Rva=0x003B6478; Hex="0920000020FE4D000B200000" },
            @{ Name="research descriptor"; Rva=0x000A86E0; Hex="83EC08803D7C177C0000" },
            @{ Name="spell descriptor"; Rva=0x000AE3B0; Hex="83EC08803DB4177C0000" },
            @{ Name="spell row"; Rva=0x000AE4D0; Hex="51535556578B7C242057" },
            @{ Name="current player"; Rva=0x00024A00; Hex="A14C547C008B40048B49" },
            @{ Name="completion name"; Rva=0x000DFFC7; Hex="57C1F91750" }
            @{ Name="AP78 Enchantments switch"; Rva=0x000A39A0; Hex="3D43524232" }
            @{ Name="AP78 Speed Tonic row string assignment"; Rva=0x000A3A08; Hex="E843491800" }
            @{ Name="stock string assignment"; Rva=0x00228350; Hex="56578B7C240C8BF1" }
            @{ Name="shared activity-text resolver"; Rva=0x00108480; Hex="56E86A6A0500" }
            @{ Name="name registry completion"; Rva=0x0011090E; Hex="8B44241C895824" }
            @{ Name="stock operator new"; Rva=0x002D8F7E; Hex="FF2540537300" }
            @{ Name="name generator factory"; Rva=0x0010C070; Hex="6AFF684E0E7000" }
            @{ Name="name generator constructor"; Rva=0x0010AB70; Hex="6AFF68FB0A7000" }
            @{ Name="name registry insertion"; Rva=0x0010FB70; Hex="8B54240483EC1053" }
            @{ Name="sovereign target manager"; Rva=0x0005E5D0; Hex="6AFF682B9C6E00" }
            @{ Name="sovereign target cancellation entry"; Rva=0x0005E9D0; Hex="8B4424045650E835BBFFFF" }
            @{ Name="sovereign cursor transition"; Rva=0x0005EE25; Hex="8B168B524889463C895E40895E388B470453508BCEFFD2" }
        )
    },
    [pscustomobject]@{
        Id = "beta2-1.5.2.28"
        Version = "1.5.2.28"
        Timestamp = [uint32]0x5A8A11D5
        Sha256 = "99848B5DB16CC3EA540D7E909CB24966AD9F3CD15D302CDE47AAB3BA81E3167E"
        Path = $Beta2Exe
        Patterns = @(
            @{ Name="secondary controller"; Rva=0x0002691A; Hex="8B6B2483C310" },
            @{ Name="dialog creation"; Rva=0x000268E0; Hex="83EC0853555657" },
            @{ Name="dialog factory"; Rva=0x0011B150; Hex="6AFF68B7907100" },
            @{ Name="AP08 constructor"; Rva=0x0009EAC0; Hex="6AFF6808737000" },
            @{ Name="AP08 vtable start"; Rva=0x00356054; Hex="80EB4900B0EE49005072490040EF4900" },
            @{ Name="AP08 vtable boundary"; Rva=0x00356084; Hex="D05A49002367616D" },
            @{ Name="MX05 GPL scalar evaluator"; Rva=0x000BC7F0; Hex="6AFF6820B17000" },
            @{ Name="MX05 post-submit control handoff"; Rva=0x000BCB97; Hex="558BCEE801CAFDFF5F" },
            @{ Name="MX05 general control handoff"; Rva=0x000BCBAE; Hex="558BCEE8EAC9FDFF5F" },
            @{ Name="MX05 row-click focus branch"; Rva=0x000995D9; Hex="8B4E248B018B50686A006A00" },
            @{ Name="MX05 post-action focus branch"; Rva=0x00099618; Hex="8B178B82B80000008BCFFFD0" },
            @{ Name="GPL integer argument adapter"; Rva=0x00178D90; Hex="83C108E9" },
            @{ Name="GPL result vector access"; Rva=0x0002ED50; Hex="83EC08558B2D" },
            @{ Name="GPL agent result resolver"; Rva=0x0016EC60; Hex="568BF18B4608" },
            @{ Name="MX05 row name call"; Rva=0x00098AB5; Hex="E846A7FAFF" },
            @{ Name="MX05 row intent call"; Rva=0x00098D6D; Hex="E8FE611300" },
            @{ Name="unknown dialog fallback"; Rva=0x0011C58F; Hex="8B4C240464890D000000005983C40CC21000CCCCCCCCCCCCCCCCCCCCCCCC" },
            @{ Name="shared guild allocation"; Rva=0x0011C3EC; Hex="6A34E84F211D00" },
            @{ Name="UI manager"; Rva=0x00026CD0; Hex="6AFF68DB5D6F0064A100" },
            @{ Name="dialog removal"; Rva=0x00026850; Hex="83EC08535556578B7C24" },
            @{ Name="panel context"; Rva=0x00068780; Hex="8B512C33C085D274098B" },
            @{ Name="command metadata"; Rva=0x001D7240; Hex="83EC0C8D042450E894FE" },
            @{ Name="player agent"; Rva=0x0002B150; Hex="A1D43F7E008B48048B11" },
            @{ Name="packed attribute"; Rva=0x001CEF70; Hex="8B5424048D4424045052" },
            @{ Name="building command"; Rva=0x000C5730; Hex="6AFF680BC9700064A100" },
            @{ Name="Rage dispatch"; Rva=0x000C5A21; Hex="8B4D0C518BCF" },
            @{ Name="Rage branch"; Rva=0x000B1B59; Hex="6841450000" },
            @{ Name="Rage GPL continuation"; Rva=0x000B1BB9; Hex="8D4C2410E85E861800C7" },
            @{ Name="game update call"; Rva=0x0002623D; Hex="E85E160000" },
            @{ Name="game update"; Rva=0x000278A0; Hex="83EC38568D442424508B" },
            @{ Name="stream control"; Rva=0x00267920; Hex="53558BE98B4544837818" },
            @{ Name="research rows"; Rva=0x000A93D0; Hex="558B6C2408578B7D04" },
            @{ Name="research row"; Rva=0x000A9160; Hex="6AFF6848887000" },
            @{ Name="research validation"; Rva=0x000A9430; Hex="8B44240453565750" },
            @{ Name="research command"; Rva=0x000C36A0; Hex="6AFF685BC27000" },
            @{ Name="research completion"; Rva=0x000E0430; Hex="6AFF6870037100" },
            @{ Name="research completion dispatch"; Rva=0x003D46D8; Hex="0920000030044E000B200000" },
            @{ Name="research descriptor"; Rva=0x000A8FD0; Hex="83EC08803D64027E0000" },
            @{ Name="spell descriptor"; Rva=0x000AECA0; Hex="83EC08803D9C027E0000" },
            @{ Name="spell row"; Rva=0x000AEDC0; Hex="51535556578B7C242057" },
            @{ Name="current player"; Rva=0x000259D0; Hex="A1D43F7E008B40048B49" },
            @{ Name="completion name"; Rva=0x000E05D7; Hex="57C1F91750" }
            @{ Name="AP78 Enchantments switch"; Rva=0x000A4280; Hex="3D43524232" }
            @{ Name="AP78 Speed Tonic row string assignment"; Rva=0x000A42E8; Hex="E803681900" }
            @{ Name="stock string assignment"; Rva=0x0023AAF0; Hex="56578B7C240C8BF1" }
            @{ Name="shared activity-text resolver"; Rva=0x0010A650; Hex="56E8DAA90600" }
            @{ Name="name registry completion"; Rva=0x00120E5E; Hex="8B44241C895824" }
            @{ Name="stock operator new"; Rva=0x002EE542; Hex="FF2580E47400" }
            @{ Name="name generator factory"; Rva=0x0011C5C0; Hex="6AFF68EE907100" }
            @{ Name="name generator constructor"; Rva=0x0011B0C0; Hex="6AFF689B8D7100" }
            @{ Name="name registry insertion"; Rva=0x001200C0; Hex="8B54240483EC1053" }
            @{ Name="sovereign target manager"; Rva=0x0005F600; Hex="6AFF683BF56F00" }
            @{ Name="sovereign target cancellation entry"; Rva=0x0005FA00; Hex="8B4424045650E835BBFFFF" }
            @{ Name="sovereign cursor transition"; Rva=0x0005FE55; Hex="8B168B524889463C895E40895E388B470453508BCEFFD2" }
        )
    }
)

foreach ($profile in $profiles) {
    $pe = Read-Pe $profile.Path
    Assert-True ($pe.FileVersion -eq $profile.Version) "Wrong version for $($profile.Id)."
    Assert-True ($pe.Timestamp -eq $profile.Timestamp) "Wrong PE timestamp for $($profile.Id)."
    if (-not $AllowModifiedReferences) {
        Assert-True ($pe.Sha256 -eq $profile.Sha256) "Wrong pristine SHA-256 for $($profile.Id)."
    }
    # Modified references still require every exact stock site below. This
    # option makes no whole-file pristine claim and never relaxes byte guards.
    foreach ($pattern in $profile.Patterns) { Assert-Pattern $pe $pattern }
    Assert-True ($runtimeSource.Contains('"' + $profile.Id + '"')) "Runtime omits $($profile.Id)."
    Assert-True ($runtimeSource.Contains(('0x{0:X8}' -f $profile.Timestamp))) "Runtime omits the $($profile.Id) timestamp."
}

Assert-True ($runtimeSource.Contains("SelectMajestyBuildProfile() || !ValidateMajestyBuildProfile()")) "Runtime does not preflight the selected profile before installation."
Assert-True ($runtimeSource.Contains("Runtime refused unknown Majesty build timestamp")) "Runtime does not fail closed on unknown builds."
Assert-True ($runtimeSource.Contains("BuildCustomGuildFactoryPatch")) "Runtime does not reproduce the proven CG-prefix stock fallback."
Assert-True ($runtimeSource.Contains("InstallCustomGuildFactoryFallback")) "Runtime does not restore the CG-prefix route after a Steam branch replacement."
Assert-True ($runtimeSource.Contains("g_buildProfile->sharedGuildControllerRva - jumpFrom")) "Runtime does not derive the branch-local stock guild allocation target."
Assert-True ($runtimeSource.Contains("InstallPrivateNameGenerators")) "Runtime does not install requested private name generators."
Assert-True ($runtimeSource.Contains("Registered private %s through Majesty's stock name-generator registry lifecycle.")) "Runtime does not preserve the traced stock name-generator lifecycle."
Assert-True ($runtimeSource.Contains("g_runtimeFeatureRegistry.nameGenerators")) "Runtime does not enumerate manager-validated private name generators."
Assert-True ($runtimeSource.Contains("record.namePartIds[0]")) "Runtime does not bind generic generators to their first HN table."
Assert-True ($runtimeSource.Contains("record.namePartIds[3]")) "Runtime does not bind generic generators to all four HN tables."
Assert-True (-not $runtimeSource.Contains("kAlchemistNameGeneratorId")) "Runtime still hardcodes the Alchemist name generator."
Assert-True (-not $runtimeSource.Contains("kPhantomNameGeneratorId")) "Runtime still hardcodes the Phantom name generator."

if ($PatchedBeta2Exe) {
    $patched = Read-Pe $PatchedBeta2Exe
    $beta2 = $profiles[1]
    Assert-True ($patched.Timestamp -eq $beta2.Timestamp) "Active executable is not the beta2 profile."
    foreach ($pattern in $beta2.Patterns) { Assert-Pattern $patched $pattern }
}

Write-Host "Validated public and beta2 runtime profiles against pristine executable fixtures."
