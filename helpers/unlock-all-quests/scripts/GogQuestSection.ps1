function Read-U16 {
    param([byte[]]$Bytes, [int]$Offset)
    return [BitConverter]::ToUInt16($Bytes, $Offset)
}

function Read-U32 {
    param([byte[]]$Bytes, [int]$Offset)
    return [BitConverter]::ToUInt32($Bytes, $Offset)
}

function Write-U32 {
    param([byte[]]$Bytes, [int]$Offset, [uint32]$Value)
    [BitConverter]::GetBytes($Value).CopyTo($Bytes, $Offset)
}

function Test-BytesEqual {
    param([byte[]]$Bytes, [int]$Offset, [byte[]]$Expected)
    if ($Offset -lt 0 -or ($Offset + $Expected.Length) -gt $Bytes.Length) { return $false }
    for ($i = 0; $i -lt $Expected.Length; $i++) {
        if ($Bytes[$Offset + $i] -ne $Expected[$i]) { return $false }
    }
    return $true
}

function Test-ZeroRange {
    param([byte[]]$Bytes, [int]$Offset, [int]$Length)
    if ($Offset -lt 0 -or ($Offset + $Length) -gt $Bytes.Length) { return $false }
    for ($i = 0; $i -lt $Length; $i++) {
        if ($Bytes[$Offset + $i] -ne 0) { return $false }
    }
    return $true
}

function Write-Bytes {
    param([byte[]]$Bytes, [int]$Offset, [byte[]]$Patch)
    if ($null -eq $Patch -or $Patch.Length -eq 0) { throw "Refusing to write an empty patch." }
    if ($Offset -lt 0 -or ($Offset + $Patch.Length) -gt $Bytes.Length) { throw "Patch range is outside the target file." }
    [Array]::Copy($Patch, 0, $Bytes, $Offset, $Patch.Length)
}

function Align-Value {
    param([uint32]$Value, [uint32]$Alignment)
    return [uint32](([uint64]([Math]::Ceiling([double]$Value / [double]$Alignment))) * [uint64]$Alignment)
}

function Get-PeInfo {
    param([byte[]]$Bytes)
    if ($Bytes.Length -lt 0x400 -or (Read-U16 $Bytes 0) -ne 0x5A4D) { throw "MajestyHD.exe is not a valid supported PE image." }
    $peOffset = [int](Read-U32 $Bytes 0x3C)
    if ($peOffset -lt 0 -or ($peOffset + 24) -gt $Bytes.Length -or (Read-U32 $Bytes $peOffset) -ne 0x4550) {
        throw "MajestyHD.exe has an invalid PE header."
    }
    $sectionCountOffset = $peOffset + 6
    $sectionCount = [int](Read-U16 $Bytes $sectionCountOffset)
    $optionalSize = [int](Read-U16 $Bytes ($peOffset + 20))
    $optionalOffset = $peOffset + 24
    $sectionTableOffset = $optionalOffset + $optionalSize
    if ((Read-U16 $Bytes ($peOffset + 4)) -ne 0x014C -or $optionalSize -ne 0xE0 -or (Read-U16 $Bytes $optionalOffset) -ne 0x010B) {
        throw "MajestyHD.exe is not the expected 32-bit x86 image."
    }
    $sizeOfHeaders = [int](Read-U32 $Bytes ($optionalOffset + 60))
    if ($sectionCount -lt 4 -or ($sectionTableOffset + ($sectionCount * 40)) -gt $sizeOfHeaders) {
        throw "MajestyHD.exe has an invalid or truncated section table."
    }
    $sections = @()
    for ($i = 0; $i -lt $sectionCount; $i++) {
        $offset = $sectionTableOffset + ($i * 40)
        $rawSize = [uint32](Read-U32 $Bytes ($offset + 16))
        $rawOffset = [uint32](Read-U32 $Bytes ($offset + 20))
        if ($rawSize -gt 0 -and ($rawOffset -lt $sizeOfHeaders -or ([uint64]$rawOffset + $rawSize) -gt $Bytes.Length)) {
            throw "MajestyHD.exe declares a section outside the file."
        }
        $sections += [pscustomobject]@{
            Index = $i
            HeaderOffset = $offset
            Name = [Text.Encoding]::ASCII.GetString($Bytes[$offset..($offset + 7)]).TrimEnd([char]0)
            VirtualSize = [uint32](Read-U32 $Bytes ($offset + 8))
            Rva = [uint32](Read-U32 $Bytes ($offset + 12))
            RawSize = $rawSize
            RawOffset = $rawOffset
            Characteristics = [uint32](Read-U32 $Bytes ($offset + 36))
        }
    }
    return [pscustomobject]@{
        PeOffset = $peOffset
        Timestamp = [uint32](Read-U32 $Bytes ($peOffset + 8))
        SectionCountOffset = $sectionCountOffset
        SectionCount = $sectionCount
        OptionalOffset = $optionalOffset
        ImageBase = [uint32](Read-U32 $Bytes ($optionalOffset + 28))
        SectionAlignment = [uint32](Read-U32 $Bytes ($optionalOffset + 32))
        FileAlignment = [uint32](Read-U32 $Bytes ($optionalOffset + 36))
        SizeOfImageOffset = $optionalOffset + 56
        SizeOfImage = [uint32](Read-U32 $Bytes ($optionalOffset + 56))
        SizeOfHeaders = $sizeOfHeaders
        SectionTableOffset = $sectionTableOffset
        Sections = $sections
    }
}


function Initialize-GogQuestSection {
    param([byte[]]$Bytes)
    if ($Bytes.Length -lt 0x400) { return $null }
    $peOffset = [BitConverter]::ToUInt32($Bytes, 0x3C)
    if ($peOffset -gt ($Bytes.Length - 24) -or [BitConverter]::ToUInt32($Bytes, $peOffset + 8) -ne 0x5BBB8DB8) { return $null }
    $pe = Get-PeInfo $Bytes
    if ($pe.ImageBase -ne 0x400000 -or $pe.FileAlignment -ne 0x200 -or $pe.SectionAlignment -ne 0x1000 -or $pe.SizeOfHeaders -ne 0x400) { throw "Unsupported GOG image layout." }
    $expected = @(
        @(".text",0x34BEFD,0x1000,0x34C000,0x400),
        @(".rdata",0x843F8,0x34D000,0x84400,0x34C400),
        @(".data",0x5908C,0x3D2000,0xD400,0x3D0800),
        @(".rsrc",0xF34,0x42C000,0x1000,0x3DDC00)
    )
    for ($i = 0; $i -lt 4; $i++) {
        $a = $pe.Sections[$i]; $e = $expected[$i]
        if ($a.Name -ne $e[0] -or $a.VirtualSize -ne $e[1] -or $a.Rva -ne $e[2] -or $a.RawSize -ne $e[3] -or $a.RawOffset -ne $e[4]) { throw "Unsupported GOG stock sections." }
    }
    $found = @($pe.Sections | Where-Object Name -eq ".muqk")
    if ($found.Count -gt 1) { throw "Duplicate Unlock All Quests sections." }
    if ($found.Count -eq 1) {
        $section = $found[0]
        if ($section.RawSize -ne 0x200 -or $section.VirtualSize -ne 0x100 -or $section.Characteristics -ne 0x60000020 -or ($section.RawOffset % 0x200) -ne 0 -or ($section.Rva % 0x1000) -ne 0) { throw "Incompatible Unlock All Quests section." }
        $header = New-GogQuestHeader $section.Rva $section.RawOffset
        if (-not (Test-BytesEqual $Bytes $section.HeaderOffset $header)) { throw "Unexpected Unlock All Quests section header." }
        # Reject aliasing/overlap with another section, including the stock image.
        foreach ($other in $pe.Sections | Where-Object Index -ne $section.Index) {
            if (($section.RawOffset -lt ($other.RawOffset + $other.RawSize) -and $other.RawOffset -lt ($section.RawOffset + 0x200)) -or
                ($section.Rva -lt ($other.Rva + [Math]::Max($other.RawSize,$other.VirtualSize)) -and $other.Rva -lt ($section.Rva + 0x1000))) { throw "Overlapping Unlock All Quests section." }
        }
        if (-not (Test-ZeroRange $Bytes ($section.RawOffset + 0xD6) (0x200 - 0xD6))) { throw "Unexpected data after the Unlock All Quests payload." }
        return [pscustomobject]@{ Bytes = $Bytes; Rva = $section.Rva; RawOffset = $section.RawOffset }
    }
    $raw = Align-Value ([uint32]$Bytes.Length) 0x200
    if ($raw -ne $Bytes.Length) { throw "Unaligned trailing executable data." }
    $end = ($pe.Sections | ForEach-Object { $_.Rva + [Math]::Max($_.RawSize,$_.VirtualSize) } | Measure-Object -Maximum).Maximum
    $rva = Align-Value ([uint32]$end) 0x1000
    $slot = $pe.SectionTableOffset + $pe.SectionCount * 40
    if (($slot + 40) -gt $pe.SizeOfHeaders -or -not (Test-ZeroRange $Bytes $slot 40)) { throw "No empty section header remains for Unlock All Quests." }
    [byte[]]$result = New-Object byte[] ($raw + 0x200)
    $Bytes.CopyTo($result,0)
    [BitConverter]::GetBytes([uint16]($pe.SectionCount + 1)).CopyTo($result,$pe.SectionCountOffset)
    Write-U32 $result $pe.SizeOfImageOffset (Align-Value ([uint32]($rva + 0x100)) 0x1000)
    (New-GogQuestHeader $rva $raw).CopyTo($result,$slot)
    return [pscustomobject]@{ Bytes = $result; Rva = $rva; RawOffset = $raw }
}

function New-GogQuestHeader {
    param([uint32]$Rva,[uint32]$RawOffset)
    [byte[]]$header = New-Object byte[] 40
    [Text.Encoding]::ASCII.GetBytes(".muqk").CopyTo($header,0)
    Write-U32 $header 8 0x100
    Write-U32 $header 12 $Rva
    Write-U32 $header 16 0x200
    Write-U32 $header 20 $RawOffset
    Write-U32 $header 36 0x60000020
    return $header
}

function Remove-GogQuestSection {
    param([byte[]]$Bytes)
    $pe = Get-PeInfo $Bytes
    $section = @($pe.Sections | Where-Object Name -eq ".muqk")[0]
    if ($null -eq $section -or -not (Test-ZeroRange $Bytes $section.RawOffset $section.RawSize)) { throw "Unlock All Quests section must be inert before removal." }
    if ($section.Index -ne ($pe.SectionCount - 1) -or ($section.RawOffset + $section.RawSize) -ne $Bytes.Length) { return $Bytes }
    [byte[]]$result = New-Object byte[] $section.RawOffset
    [Array]::Copy($Bytes,0,$result,0,$result.Length)
    [Array]::Clear($result,$section.HeaderOffset,40)
    [BitConverter]::GetBytes([uint16]($pe.SectionCount - 1)).CopyTo($result,$pe.SectionCountOffset)
    $end = ($pe.Sections | Where-Object Index -ne $section.Index | ForEach-Object { $_.Rva + [Math]::Max($_.RawSize,$_.VirtualSize) } | Measure-Object -Maximum).Maximum
    Write-U32 $result $pe.SizeOfImageOffset (Align-Value ([uint32]$end) 0x1000)
    return $result
}
function New-GogQuestJump {
    param([uint32]$Source,[uint32]$Target,[int]$Size)
    [byte[]]$result = New-Object byte[] $Size
    for ($i=0; $i -lt $Size; $i++) { $result[$i]=0x90 }
    $result[0]=0xE9
    [BitConverter]::GetBytes([int]([int64]$Target - $Source - 5)).CopyTo($result,1)
    return $result
}

function Get-GogUnlockProfile {
    param([object]$Section)
    $va = [uint32](0x400000 + $Section.Rva)
    [byte[]]$blob = [Convert]::FromBase64String("oLSwggCEwHQDwgQAav9oWH9xAOnC+t3/ZoH7mgJ1GYgdtLCCAGBqAIn56JS20v+DxARh6UTA0v+B+4oTAADpz8LS/wAAAAAAAAAAAAAAAABgMcCitLCCAGoAifnoYrbS/4PEBGEx9jmcJLgAAADpLcTS/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==")
    [BitConverter]::GetBytes([int]([int64]0x51DA47 - $va - 24)).CopyTo($blob,20)
    [BitConverter]::GetBytes([int]([int64]0x478BB0 - $va - 47)).CopyTo($blob,43)
    [BitConverter]::GetBytes([int]([int64]0x479569 - $va - 56)).CopyTo($blob,52)
    [BitConverter]::GetBytes([int]([int64]0x47980F - $va - 67)).CopyTo($blob,63)
    [BitConverter]::GetBytes([int]([int64]0x478BB0 - $va - 97)).CopyTo($blob,93)
    [BitConverter]::GetBytes([int]([int64]0x47999D - $va - 115)).CopyTo($blob,111)
    return [pscustomobject]@{
        Id = "gog"
        DisplayName = "GOG Gold HD (1.5.2.28)"
        CaveOffset = $Section.RawOffset; CaveSize = 0xD6
        EligibilityHookOffset = 0x11CE40; DispatchHookOffset = 0x78C09
        ResetRefreshHookOffset = 0x78D94; VisibilityImmediateOffset = 0x784CD
        EligibilityOriginal = [byte[]]@(0x6A,0xFF,0x68,0x58,0x7F,0x71,0)
        DispatchOriginal = [byte[]]@(0x81,0xFB,0x8A,0x13,0,0)
        ResetRefreshOriginal = [byte[]]@(0x33,0xF6,0x39,0x9C,0x24,0xB8,0,0,0)
        EligibilityHook = New-GogQuestJump 0x51DA40 $va 7
        DispatchHook = New-GogQuestJump 0x479809 ($va + 24) 6
        ResetRefreshHook = New-GogQuestJump 0x479994 ($va + 80) 9
        PatchBlobBase64 = [Convert]::ToBase64String($blob)
    }
}
