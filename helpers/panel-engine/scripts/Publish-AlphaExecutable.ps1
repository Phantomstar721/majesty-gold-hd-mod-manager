param(
    [Parameter(Mandatory=$true)][string]$Original,
    [Parameter(Mandatory=$true)][string]$Candidate,
    [Parameter(Mandatory=$true)][string]$CandidateHash,
    [Parameter(Mandatory=$true)][string]$PreviousHash,
    [string]$UIManifest=''
)
$ErrorActionPreference='Stop'
function FileDigest([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
$source=(Get-Item -LiteralPath $Original).FullName
if ([IO.Path]::GetFileName($source) -ine 'MajestyHD.exe') { throw 'Choose the original MajestyHD.exe.' }
$target=Join-Path ([IO.Path]::GetDirectoryName($source)) 'MajestyHD.PanelEngineAlpha.exe'
if ((FileDigest $Candidate) -ine $CandidateHash) { throw 'Alpha candidate changed.' }
$previous=if (Test-Path -LiteralPath $target) { FileDigest $target } else { 'absent' }
if ($previous -ine $PreviousHash) { throw 'Alpha executable changed during review. Refresh its status.' }
$plan=New-Object System.Collections.Generic.List[object]
$seen=@{}
if ($UIManifest) {
    $rows=[IO.File]::ReadAllText($UIManifest) | ConvertFrom-Json
    foreach ($row in $rows) {
        if ($row.name -notmatch '^UIAlfa_[0-9]+_[0-9]+\.dat$' -or $seen.ContainsKey($row.name)) { throw 'Invalid or duplicate alpha layout filename.' }
        $seen[$row.name]=$true
        $destination=Join-Path (Join-Path ([IO.Path]::GetDirectoryName($source)) 'Data') $row.name
        $plan.Add(@{target=$destination;candidate=[string]$row.candidate;sha256=[string]$row.sha256;previous=[string]$row.previous})
    }
}
# Publish the EXE last: its private filename becomes active only after every
# resolution layout is present. All targets and locks are checked first.
$plan.Add(@{target=$target;candidate=$Candidate;sha256=$CandidateHash;previous=$PreviousHash})
foreach ($item in $plan) {
    if ((FileDigest $item.candidate) -ine $item.sha256) { throw 'Alpha publication input changed.' }
    $actual=if (Test-Path -LiteralPath $item.target) { FileDigest $item.target } else { 'absent' }
    if ($actual -ine $item.previous) { throw 'Alpha files changed during review. Refresh their status.' }
    if ($actual -ne 'absent') {
        $probe=[IO.File]::Open($item.target,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        $probe.Dispose()
    }
    $directory=[IO.Path]::GetDirectoryName($item.target)
    $token='.panel-alpha-'+[Guid]::NewGuid().ToString('N')
    $item.temporary=Join-Path $directory ($token+'.tmp')
    $item.backup=Join-Path $directory ($token+'.bak')
}
$committed=New-Object System.Collections.Generic.List[object]
$publicationComplete=$false
$rollbackComplete=$false
try {
    foreach ($item in $plan) {
        [IO.File]::Copy($item.candidate,$item.temporary,$false)
        if ((FileDigest $item.temporary) -ine $item.sha256) { throw 'Alpha copy verification failed.' }
    }
    foreach ($item in $plan) {
        if ($item.previous -ne 'absent') { [IO.File]::Replace($item.temporary,$item.target,$item.backup) }
        else { [IO.File]::Move($item.temporary,$item.target) }
        $committed.Add($item)
    }
    $publicationComplete=$true
} catch {
    for ($i=$committed.Count-1;$i -ge 0;$i--) {
        $item=$committed[$i]
        if ((FileDigest $item.target) -ine $item.sha256) { throw 'Alpha rollback refused: a published file changed externally.' }
        if ($item.previous -eq 'absent') { [IO.File]::Delete($item.target) }
        else { [IO.File]::Replace($item.backup,$item.target,[NullString]::Value) }
    }
    $rollbackComplete=$true
    throw
} finally {
    foreach ($item in $plan) {
        $cleanup=@($item.temporary)
        if ($publicationComplete -or $rollbackComplete) { $cleanup+=@($item.backup) }
        foreach ($file in $cleanup) {
            if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
        }
    }
}
