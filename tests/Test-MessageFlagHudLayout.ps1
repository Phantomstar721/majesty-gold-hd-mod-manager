$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $repoRoot 'artifacts\message-flag-hud-tests'
$toolRoot = 'C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023'
$sdk = 'C:\Program Files (x86)\Windows Kits\10'
$inc = Get-ChildItem (Join-Path $sdk 'Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$lib = Get-ChildItem (Join-Path $sdk 'Lib') -Directory | Sort-Object Name -Descending | Select-Object -First 1
New-Item -ItemType Directory -Path $output -Force | Out-Null
$compiler = Join-Path $toolRoot 'bin\Hostx86\x86\cl.exe'
$log = Join-Path $output 'compile.log'
& $compiler /nologo /W4 /O2 /EHsc "/I$toolRoot\include" "/I$($inc.FullName)\ucrt" `
    (Join-Path $PSScriptRoot 'MessageFlagHudLayoutTests.cpp') "/Fo$output\" `
    "/Fe:$output\MessageFlagHudLayoutTests.exe" /link "/LIBPATH:$toolRoot\lib\x86" `
    "/LIBPATH:$($lib.FullName)\ucrt\x86" "/LIBPATH:$($lib.FullName)\um\x86" *> $log
if ($LASTEXITCODE -ne 0) { Get-Content $log; throw 'HUD layout tests did not compile.' }
