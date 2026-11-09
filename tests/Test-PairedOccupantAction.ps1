$ErrorActionPreference = 'Stop'
$pairRepo = Split-Path -Parent $PSScriptRoot
$pairOutput = Join-Path $pairRepo 'artifacts\paired-occupant-test'
$pairTools = 'C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023'
$pairSdk = 'C:\Program Files (x86)\Windows Kits\10'
$pairVersion = (Get-ChildItem "$pairSdk\Include" -Directory | Sort-Object Name -Descending | Select-Object -First 1).Name
New-Item -ItemType Directory -Force $pairOutput | Out-Null
$pairIncludes = @("/I$pairTools\include", "/I$pairSdk\Include\$pairVersion\ucrt")
$pairLibraries = @("/LIBPATH:$pairTools\lib\x86", "/LIBPATH:$pairSdk\Lib\$pairVersion\ucrt\x86", "/LIBPATH:$pairSdk\Lib\$pairVersion\um\x86")
$pairLog = & "$pairTools\bin\Hostx86\x86\cl.exe" /nologo /W4 /O2 /EHsc @pairIncludes `
    (Join-Path $PSScriptRoot 'PairedOccupantActionTests.cpp') "/Fo$pairOutput\" "/Fe:$pairOutput\PairedOccupantActionTests.exe" /link @pairLibraries 2>&1
if ($LASTEXITCODE -ne 0) { throw "Paired action compile failed: $pairLog" }
& "$pairOutput\PairedOccupantActionTests.exe"
if ($LASTEXITCODE -ne 0) { throw 'Paired action ABI fixture failed' }
$pairPreviousPythonPath = $env:PYTHONPATH
Push-Location $pairRepo
try {
    $env:PYTHONPATH = 'src;tests'
    foreach ($pairSuite in @('test_building_employment.py', 'test_employment_command_profiles.py', 'test_action_callback_bridge.py')) {
        $pairLog = & '.venv/Scripts/python.exe' -m unittest discover -s tests -p $pairSuite -q 2>&1
        if ($LASTEXITCODE -ne 0) { throw "$pairSuite failed: $pairLog" }
    }
} finally {
    $env:PYTHONPATH = $pairPreviousPythonPath
    Pop-Location
}
