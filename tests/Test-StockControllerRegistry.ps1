$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$output = Join-Path $repoRoot "artifacts\stock-controller-registry-test"
$toolRoot = "C:\Program Files (x86)\Microsoft Visual Studio\2017\BuildTools\VC\Tools\MSVC\14.16.27023"
$compiler = Join-Path $toolRoot "bin\Hostx86\x86\cl.exe"
$include = Join-Path $toolRoot "include"
$windowsSdk = "C:\Program Files (x86)\Windows Kits\10"
$sdkIncludeVersion = Get-ChildItem (Join-Path $windowsSdk "Include") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1
$sdkLibVersion = Get-ChildItem (Join-Path $windowsSdk "Lib") -Directory |
    Sort-Object Name -Descending | Select-Object -First 1

try {
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    $includes = @(
        "/I$include",
        "/I$($sdkIncludeVersion.FullName)\ucrt",
        "/I$($sdkIncludeVersion.FullName)\shared",
        "/I$($sdkIncludeVersion.FullName)\um"
    )
    $libraries = @(
        "/LIBPATH:$toolRoot\lib\x86",
        "/LIBPATH:$($sdkLibVersion.FullName)\ucrt\x86",
        "/LIBPATH:$($sdkLibVersion.FullName)\um\x86"
    )
    & $compiler /nologo /W4 /O2 /EHsc @includes `
        (Join-Path $repoRoot "runtime\StockControllerRegistry.cpp") `
        (Join-Path $repoRoot "tests\StockControllerRegistryTests.cpp") `
        "/Fo$output\" "/Fe:$output\StockControllerRegistryTests.exe" /link @libraries
    if ($LASTEXITCODE -ne 0) {
        throw "Stock controller parser test build failed with exit code $LASTEXITCODE"
    }
    & (Join-Path $output "StockControllerRegistryTests.exe")
    if ($LASTEXITCODE -ne 0) {
        throw "Stock controller parser tests failed with exit code $LASTEXITCODE"
    }
}
finally {
    if (Test-Path -LiteralPath $output) {
        Remove-Item -LiteralPath $output -Recurse -Force
    }
}
