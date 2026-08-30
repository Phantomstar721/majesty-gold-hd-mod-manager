param(
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD",
    [string]$RuntimeRoot = ".\artifacts\runtime",
    [Parameter(Mandatory = $true)]
    [string]$ReportRoot,
    [string]$SavePath = "",
    [string[]]$GameArguments = @("-debugout")
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = if ([IO.Path]::IsPathRooted($RuntimeRoot)) {
    $RuntimeRoot
} else {
    Join-Path $repoRoot $RuntimeRoot
}
$reportBase = if ([IO.Path]::IsPathRooted($ReportRoot)) {
    $ReportRoot
} else {
    Join-Path $repoRoot $ReportRoot
}
if ([string]::IsNullOrWhiteSpace($SavePath)) {
    $documents = [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)
    $SavePath = Join-Path $documents "My Games\MajestyHD\SaveGame\autosave.GMP"
}
$majestyRoot = Split-Path -Parent (Split-Path -Parent $SavePath)

$launcher = Join-Path $runtime "MajestyBuildingRuntimeLauncher.exe"
$dll = Join-Path $runtime "MajestyBuildingRuntime.dll"
$game = Join-Path $GamePath "MajestyHD.exe"
foreach ($path in @($launcher, $dll, $game)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required diagnostic file was not found: $path"
    }
}
if (Get-Process -Name "MajestyHD" -ErrorAction SilentlyContinue) {
    throw "MajestyHD.exe is already running. Fully close it before starting the diagnostic run."
}

$session = Join-Path $reportBase (Get-Date -Format "yyyy-MM-dd-HHmmss")
New-Item -ItemType Directory -Path $session -Force | Out-Null
if (Test-Path -LiteralPath $SavePath -PathType Leaf) {
    Copy-Item -LiteralPath $SavePath -Destination (Join-Path $session "autosave-before.GMP")
}
$runtimeLog = Join-Path $runtime "MajestyBuildingRuntime.log"
$gplLog = Join-Path $majestyRoot "Logs\gpl.log"
$runtimeLogStart = if (Test-Path -LiteralPath $runtimeLog -PathType Leaf) {
    (Get-Item -LiteralPath $runtimeLog).Length
} else { 0 }
$gplLogStart = if (Test-Path -LiteralPath $gplLog -PathType Leaf) {
    (Get-Item -LiteralPath $gplLog).Length
} else { 0 }

function Copy-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][long]$Start
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }
    $inputStream = [IO.File]::Open($Source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        if ($Start -gt $inputStream.Length) {
            $Start = 0
        }
        [void]$inputStream.Seek($Start, [IO.SeekOrigin]::Begin)
        $outputStream = [IO.File]::Open($Destination, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        try {
            $inputStream.CopyTo($outputStream)
        } finally {
            $outputStream.Close()
        }
    } finally {
        $inputStream.Close()
    }
}

$registrySubkey = "Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\MajestyHD.exe"
$valueNames = @("DumpFolder", "DumpType", "DumpCount")
$priorValues = @{}
$priorKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registrySubkey, $false)
$hadRegistryKey = $null -ne $priorKey
if ($null -ne $priorKey) {
    foreach ($name in $valueNames) {
        if ($priorKey.GetValueNames() -contains $name) {
            $priorValues[$name] = @{
                Value = $priorKey.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                Kind = $priorKey.GetValueKind($name)
            }
        }
    }
    $priorKey.Close()
}

$startedAt = Get-Date
$process = $null
try {
    $dumpKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registrySubkey)
    $dumpKey.SetValue("DumpFolder", $session, [Microsoft.Win32.RegistryValueKind]::ExpandString)
    $dumpKey.SetValue("DumpType", 2, [Microsoft.Win32.RegistryValueKind]::DWord)
    $dumpKey.SetValue("DumpCount", 10, [Microsoft.Win32.RegistryValueKind]::DWord)
    $dumpKey.Close()

    & $launcher $game $dll @GameArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime launcher failed with exit code $LASTEXITCODE"
    }

    for ($attempt = 0; $attempt -lt 40 -and $null -eq $process; $attempt++) {
        $process = Get-Process -Name "MajestyHD" -ErrorAction SilentlyContinue |
            Sort-Object StartTime -Descending |
            Select-Object -First 1
        if ($null -eq $process) {
            Start-Sleep -Milliseconds 250
        }
    }
    if ($null -eq $process) {
        throw "MajestyHD.exe did not remain running after launch."
    }

    Write-Host "Diagnostic capture is active. Start or load the intended test game."
    Write-Host "Evidence folder: $session"
    Wait-Process -Id $process.Id

    # WER normally finishes the dump before process teardown. Allow a short
    # bounded tail for the file to become visible before restoring LocalDumps.
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $dump = Get-ChildItem -LiteralPath $session -Filter "*.dmp" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -ne $dump) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    $restoreKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($registrySubkey)
    foreach ($name in $valueNames) {
        $restoreKey.DeleteValue($name, $false)
        if ($priorValues.ContainsKey($name)) {
            $prior = $priorValues[$name]
            $restoreKey.SetValue($name, $prior.Value, $prior.Kind)
        }
    }
    $restoreKey.Close()
    if (-not $hadRegistryKey) {
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($registrySubkey, $false)
    }

    if (Test-Path -LiteralPath $runtimeLog -PathType Leaf) {
        Copy-Item -LiteralPath $runtimeLog -Destination (Join-Path $session "MajestyBuildingRuntime.log") -Force
        Copy-LogTail -Source $runtimeLog -Destination (Join-Path $session "MajestyBuildingRuntime-session.log") -Start $runtimeLogStart
    }
    if (Test-Path -LiteralPath $gplLog -PathType Leaf) {
        Copy-Item -LiteralPath $gplLog -Destination (Join-Path $session "gpl.log") -Force
        Copy-LogTail -Source $gplLog -Destination (Join-Path $session "gpl-session.log") -Start $gplLogStart
    }
    Get-ChildItem -LiteralPath $GamePath -Filter "majestyhd_crash_*.mdmp" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $startedAt.AddSeconds(-2) } |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $session $_.Name) -Force
        }
    if (Test-Path -LiteralPath $SavePath -PathType Leaf) {
        Copy-Item -LiteralPath $SavePath -Destination (Join-Path $session "autosave-after.GMP") -Force
    }
    $preferences = Join-Path $majestyRoot "MajXPrefs"
    if (Test-Path -LiteralPath $preferences -PathType Leaf) {
        Copy-Item -LiteralPath $preferences -Destination (Join-Path $session "MajXPrefs") -Force
    }
    $endedAt = Get-Date
    @(
        "started=$($startedAt.ToString('o'))"
        "ended=$($endedAt.ToString('o'))"
        "game=$game"
        "runtime=$dll"
        "arguments=$($GameArguments -join ' ')"
        "save=$SavePath"
    ) | Set-Content -LiteralPath (Join-Path $session "session.txt") -Encoding UTF8
}

$fullDump = Get-ChildItem -LiteralPath $session -Filter "*.dmp" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -ne $fullDump) {
    Write-Host "Full crash dump captured: $($fullDump.FullName)"
} else {
    Write-Host "No full crash dump was produced. This is expected after a clean exit."
}
Write-Host "Diagnostic evidence collected in: $session"
