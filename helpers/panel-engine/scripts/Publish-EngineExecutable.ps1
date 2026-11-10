param(
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$Candidate,
    [Parameter(Mandatory=$true)][string]$CandidateHash,
    [Parameter(Mandatory=$true)][string]$PreviousHash
)
$ErrorActionPreference='Stop'
function FileDigest([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
$destination=(Get-Item -LiteralPath $Target).FullName
if ([IO.Path]::GetFileName($destination) -ine 'MajestyHD.exe') { throw 'Choose MajestyHD.exe.' }
if ((FileDigest $Candidate) -ine $CandidateHash) { throw 'Engine candidate changed.' }
if ((FileDigest $destination) -ine $PreviousHash) { throw 'Majesty changed during review. Refresh its status.' }
$probe=[IO.File]::Open($destination,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$probe.Dispose()
$directory=[IO.Path]::GetDirectoryName($destination)
$token='.manager-engine-'+[Guid]::NewGuid().ToString('N')
$temporary=Join-Path $directory ($token+'.tmp')
$backup=Join-Path $directory ($token+'.bak')
try {
    [IO.File]::Copy($Candidate,$temporary,$false)
    if ((FileDigest $temporary) -ine $CandidateHash) { throw 'Engine copy verification failed.' }
    if ((FileDigest $destination) -ine $PreviousHash) { throw 'Majesty changed before publication.' }
    [IO.File]::Replace($temporary,$destination,$backup)
} finally {
    foreach ($file in @($temporary,$backup)) {
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
}
