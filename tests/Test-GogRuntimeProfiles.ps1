param(
    [Parameter(Mandatory = $true)][string[]]$Executable,
    [string]$RegistryRoot = ""
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $repoRoot 'artifacts\gog-profile-tests'
$toolRoot = 'C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023'
$compiler = Join-Path $toolRoot 'bin\Hostx86\x86\cl.exe'
$sdkRoot = 'C:\Program Files (x86)\Windows Kits\10'
$sdkIncludes = Get-ChildItem (Join-Path $sdkRoot 'Include') -Directory | Sort-Object Name -Descending | Select-Object -First 1
$sdkLibs = Get-ChildItem (Join-Path $sdkRoot 'Lib') -Directory | Sort-Object Name -Descending | Select-Object -First 1
New-Item -ItemType Directory -Path $output -Force | Out-Null
$includes = @("/I$toolRoot\include", "/I$($sdkIncludes.FullName)\ucrt", "/I$($sdkIncludes.FullName)\shared", "/I$($sdkIncludes.FullName)\um")
$libraries = @("/LIBPATH:$toolRoot\lib\x86", "/LIBPATH:$($sdkLibs.FullName)\ucrt\x86", "/LIBPATH:$($sdkLibs.FullName)\um\x86")
$sources = @('BoundedMapQuery', 'MapQueryRuntime', 'EquipmentRuntime', 'ControllerLifecycleRegistry', 'FreestyleCamRuntime', 'IntentTextRegistry', 'RuntimeCapabilityManifest', 'RuntimeFeatureRegistry', 'StockControllerRegistry') | ForEach-Object { Join-Path $repoRoot "runtime\$_.cpp" }
& $compiler /nologo /W4 /O2 /EHsc @includes @sources (Join-Path $PSScriptRoot 'GogRuntimeProfileTests.cpp') (Join-Path $PSScriptRoot 'GogFixtureMemory.cpp') "/Fo$output\" "/Fe:$output\GogRuntimeProfileTests.exe" /link /BASE:0x10000000 /ALIGN:65536 /DYNAMICBASE:NO @libraries user32.lib
if ($LASTEXITCODE -ne 0) { throw "GOG profile tests did not compile: $LASTEXITCODE" }
# Relink the test image so its dedicated fixture section starts at the game's
# preferred base. Main-image reservation happens before any low-address heaps.
$testExe = Join-Path $output 'GogRuntimeProfileTests.exe'
[byte[]]$testBytes = [IO.File]::ReadAllBytes($testExe)
$pe = [BitConverter]::ToInt32($testBytes, 0x3C)
$sectionCount = [BitConverter]::ToUInt16($testBytes, $pe + 6)
$table = $pe + 24 + [BitConverter]::ToUInt16($testBytes, $pe + 20)
$fixtureRva = 0
for ($i = 0; $i -lt $sectionCount; $i++) {
    $offset = $table + 40 * $i
    if ([Text.Encoding]::ASCII.GetString($testBytes, $offset, 8) -eq '.fixture') {
        $fixtureRva = [BitConverter]::ToUInt32($testBytes, $offset + 12)
    }
}
if ($fixtureRva -eq 0 -or $fixtureRva -ge 0x400000 -or ($fixtureRva % 65536) -ne 0) { throw 'Invalid test fixture section' }
$testBase = '0x{0:X}' -f (0x400000 - $fixtureRva)
$objects = @($sources | ForEach-Object { Join-Path $output (([IO.Path]::GetFileNameWithoutExtension($_)) + '.obj') })
$objects += @((Join-Path $output 'GogRuntimeProfileTests.obj'), (Join-Path $output 'GogFixtureMemory.obj'))
& $compiler /nologo @objects "/Fe:$testExe" /link "/BASE:$testBase" /ALIGN:65536 /DYNAMICBASE:NO @libraries user32.lib
if ($LASTEXITCODE -ne 0) { throw "GOG fixture layout did not link: $LASTEXITCODE" }
$testArguments = @($Executable)
if ($RegistryRoot) { $testArguments += @('--registries', $RegistryRoot) }
& (Join-Path $output 'GogRuntimeProfileTests.exe') @testArguments
if ($LASTEXITCODE -ne 0) { throw "GOG profile tests failed: $LASTEXITCODE" }
