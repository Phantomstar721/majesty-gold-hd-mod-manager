$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $repoRoot "artifacts\occupant-action-runtime-test"
$toolRoot = "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023"
$compiler = Join-Path $toolRoot "bin\Hostx86\x86\cl.exe"
$sdkRoot = "C:\Program Files (x86)\Windows Kits\10"
$sdkIncludes = Get-ChildItem (Join-Path $sdkRoot "Include") -Directory | Sort-Object Name -Descending | Select-Object -First 1
$sdkLibs = Get-ChildItem (Join-Path $sdkRoot "Lib") -Directory | Sort-Object Name -Descending | Select-Object -First 1
New-Item -ItemType Directory -Path $output -Force | Out-Null
$includes = @("/I$toolRoot\include", "/I$($sdkIncludes.FullName)\ucrt", "/I$($sdkIncludes.FullName)\shared", "/I$($sdkIncludes.FullName)\um")
$libraries = @("/LIBPATH:$toolRoot\lib\x86", "/LIBPATH:$($sdkLibs.FullName)\ucrt\x86", "/LIBPATH:$($sdkLibs.FullName)\um\x86")
$sources = @("BoundedMapQuery", "MapQueryRuntime", "EquipmentRuntime", "ControllerLifecycleRegistry", "FreestyleCamRuntime", "IntentTextRegistry", "RuntimeCapabilityManifest", "RuntimeFeatureRegistry", "StockControllerRegistry") | ForEach-Object { Join-Path $repoRoot "runtime\$_.cpp" }
& $compiler /nologo /W4 /O2 /EHsc @includes @sources (Join-Path $PSScriptRoot "OccupantActionRuntimeTests.cpp") "/Fo$output\" "/Fe:$output\OccupantActionRuntimeTests.exe" /link @libraries user32.lib
if ($LASTEXITCODE -ne 0) { throw "Occupant runtime tests did not compile: $LASTEXITCODE" }
& (Join-Path $output "OccupantActionRuntimeTests.exe")
if ($LASTEXITCODE -ne 0) { throw "Occupant runtime tests failed: $LASTEXITCODE" }
& $compiler /nologo /W4 /O2 /EHsc @includes (Join-Path $PSScriptRoot "BoundedMapQueryTests.cpp") "/Fo$output\" "/Fe:$output\BoundedMapQueryTests.exe" /link @libraries
if ($LASTEXITCODE -ne 0) { throw "Map query tests did not compile: $LASTEXITCODE" }
& (Join-Path $output "BoundedMapQueryTests.exe")
if ($LASTEXITCODE -ne 0) { throw "Map query tests failed: $LASTEXITCODE" }
