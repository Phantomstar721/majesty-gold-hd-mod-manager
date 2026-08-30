$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$toolRoot = "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023"
$compiler = Join-Path $toolRoot "bin\Hostx86\x86\cl.exe"
$windowsSdk = "C:\Program Files (x86)\Windows Kits\10"
$sdkIncludeVersion = Get-ChildItem (Join-Path $windowsSdk "Include") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
$sdkLibVersion = Get-ChildItem (Join-Path $windowsSdk "Lib") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
$output = Join-Path $repoRoot "artifacts\controller-lifecycle-tests"

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "x86 MSVC compiler was not found: $compiler"
}
New-Item -ItemType Directory -Path $output -Force | Out-Null

$includes = @(
    "/I$(Join-Path $toolRoot 'include')",
    "/I$(Join-Path $repoRoot 'runtime')",
    "/I$($sdkIncludeVersion.FullName)\ucrt",
    "/I$($sdkIncludeVersion.FullName)\shared",
    "/I$($sdkIncludeVersion.FullName)\um"
)
$libraries = @(
    "/LIBPATH:$toolRoot\lib\x86",
    "/LIBPATH:$($sdkLibVersion.FullName)\ucrt\x86",
    "/LIBPATH:$($sdkLibVersion.FullName)\um\x86",
    "user32.lib"
)

& $compiler /nologo /W4 /EHsc @includes `
    (Join-Path $repoRoot "runtime\ControllerLifecycleRegistry.cpp") `
    (Join-Path $repoRoot "tests\ControllerLifecycleRegistryTests.cpp") `
    "/Fo$output\" "/Fe:$output\ControllerLifecycleRegistryTests.exe" /link @libraries
if ($LASTEXITCODE -ne 0) {
    throw "Controller lifecycle tests failed to compile with exit code $LASTEXITCODE"
}

& (Join-Path $output "ControllerLifecycleRegistryTests.exe")
if ($LASTEXITCODE -ne 0) {
    throw "Controller lifecycle tests failed with exit code $LASTEXITCODE"
}
