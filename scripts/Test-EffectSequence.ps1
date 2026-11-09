param([switch]$ExportSamples, [switch]$FadeLifecycle)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$out = Join-Path $repo 'artifacts\dawnfall-v2-engineering\sequence-tests'
# Local shared tools contain no C++ compiler; use the installed compiler through
# its explicit discovered path, never download or search arbitrary PATH entries.
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $install) { throw 'Installed MSVC tools were not found.' }
$tool = Get-ChildItem (Join-Path $install 'VC\Tools\MSVC') -Directory |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
$sdk = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10'
$version = Get-ChildItem (Join-Path $sdk 'Include') -Directory |
    Sort-Object Name -Descending | Where-Object {
        (Test-Path (Join-Path $_.FullName 'ucrt')) -and
        (Test-Path (Join-Path $sdk "Lib\$($_.Name)\um\x86"))
    } | Select-Object -First 1
if (-not $tool -or -not $version) { throw 'Installed x86 compiler/SDK is incomplete.' }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$compilerArgs = @('/nologo','/std:c++17','/W4','/WX','/EHsc',
    "/I$($tool.FullName)\include", "/I$($version.FullName)\ucrt",
    (Join-Path $repo 'runtime\EffectSequence.cpp'),
    (Join-Path $repo 'tests\EffectSequenceTests.cpp'),
    "/Fo$out\", "/Fe:$out\EffectSequenceTests.exe", '/link',
    "/LIBPATH:$($tool.FullName)\lib\x86", "/LIBPATH:$sdk\Lib\$($version.Name)\ucrt\x86",
    "/LIBPATH:$sdk\Lib\$($version.Name)\um\x86")
& (Join-Path $tool.FullName 'bin\Hostx86\x86\cl.exe') @compilerArgs *> (Join-Path $out 'build.log')
if ($LASTEXITCODE -ne 0) {
    Get-Content (Join-Path $out 'build.log')
    throw 'Effect sequence fixture compilation failed; see build.log.'
}
& (Join-Path $out 'EffectSequenceTests.exe')
if ($LASTEXITCODE -ne 0) { throw 'Effect sequence fixture failed.' }

$cleanupArgs = @($compilerArgs | ForEach-Object {
    if ($_ -eq (Join-Path $repo 'runtime\EffectSequence.cpp')) {
        Join-Path $repo 'runtime\CheckedPlacement.cpp'
    }
    elseif ($_ -eq (Join-Path $repo 'tests\EffectSequenceTests.cpp')) {
        Join-Path $repo 'tests\CosmeticActionCleanupTests.cpp'
    } elseif ($_ -eq "/Fe:$out\EffectSequenceTests.exe") {
        "/Fe:$out\CosmeticActionCleanupTests.exe"
    } else { $_ }
})
& (Join-Path $tool.FullName 'bin\Hostx86\x86\cl.exe') @cleanupArgs *> (Join-Path $out 'cleanup-build.log')
if ($LASTEXITCODE -ne 0) {
    Get-Content (Join-Path $out 'cleanup-build.log')
    throw 'Cosmetic cancellation fixture compilation failed.'
}
& (Join-Path $out 'CosmeticActionCleanupTests.exe')
if ($LASTEXITCODE -ne 0) { throw 'Cosmetic cancellation fixture failed.' }

if ($ExportSamples) {
    $exportArgs = @($compilerArgs | ForEach-Object {
        if ($_ -eq (Join-Path $repo 'tests\EffectSequenceTests.cpp')) {
            Join-Path $repo 'scripts\Export-EffectSequence.cpp'
        } elseif ($_ -eq "/Fe:$out\EffectSequenceTests.exe") {
            "/Fe:$out\Export-EffectSequence.exe"
        } else { $_ }
    })
    & (Join-Path $tool.FullName 'bin\Hostx86\x86\cl.exe') @exportArgs *> (Join-Path $out 'export-build.log')
    if ($LASTEXITCODE -ne 0) {
        Get-Content (Join-Path $out 'export-build.log')
        throw 'Effect sequence exporter compilation failed.'
    }
    $samples = & (Join-Path $out 'Export-EffectSequence.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Effect sequence export failed.' }
    $null = $samples | ConvertFrom-Json
    [IO.File]::WriteAllText((Join-Path $out 'samples.json'), ($samples -join "`n"), [Text.UTF8Encoding]::new($false))
}

if ($FadeLifecycle) {
    foreach ($name in @('MAJESTY_BETA2_EXE','MAJESTY_PUBLIC_EXE','MAJESTY_GOG_EXE')) {
        $fixture = [Environment]::GetEnvironmentVariable($name)
        if (-not $fixture -or -not (Test-Path -LiteralPath $fixture -PathType Leaf)) {
            throw "Required fade lifecycle fixture is missing: $name"
        }
    }
    $fadeArgs = @($compilerArgs | ForEach-Object {
        if ($_ -eq (Join-Path $repo 'runtime\EffectSequence.cpp')) { }
        elseif ($_ -eq (Join-Path $repo 'tests\EffectSequenceTests.cpp')) {
            Join-Path $repo 'tests\FadeOrderLifecycleTests.cpp'
        } elseif ($_ -eq "/Fe:$out\EffectSequenceTests.exe") {
            "/Fe:$out\FadeOrderLifecycleTests.exe"
        } else { $_ }
    })
    $fadeArgs = @("/I$($version.FullName)\um", "/I$($version.FullName)\shared") + $fadeArgs
    & (Join-Path $tool.FullName 'bin\Hostx86\x86\cl.exe') @fadeArgs *> (Join-Path $out 'fade-build.log')
    if ($LASTEXITCODE -ne 0) {
        Get-Content (Join-Path $out 'fade-build.log')
        throw 'Fade lifecycle fixture compilation failed.'
    }
    & (Join-Path $out 'FadeOrderLifecycleTests.exe') $env:MAJESTY_BETA2_EXE $env:MAJESTY_PUBLIC_EXE $env:MAJESTY_GOG_EXE
    if ($LASTEXITCODE -ne 0) { throw 'Fade lifecycle fixture failed.' }
    $python = Join-Path $repo '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python is required for persistence verification.' }
    Push-Location $repo
    try {
        $previousDamageFixtures = $env:MAJESTY_REQUIRE_DAMAGE_FIXTURES
        $env:MAJESTY_REQUIRE_DAMAGE_FIXTURES = '1'
        & $python -m unittest discover -s tests -p test_damage_contributions.py -q *> (Join-Path $out 'damage-contributions.log')
        if ($LASTEXITCODE -ne 0) {
            Get-Content (Join-Path $out 'damage-contributions.log')
            throw 'Destination-stock damage contribution verification failed.'
        }
        foreach ($test in @('test_timed_imag.py','test_paid_acquisition_profiles.py','test_native_impact_profiles.py','test_native_impact.py','test_fade_persistence_profiles.py','test_checked_relocation_profiles.py','test_dawnfall_load_profiles.py','test_checked_cast_profiles.py','test_observation_native_profiles.py','test_observer_body_profiles.py','test_attack_observation_profiles.py','test_placement_binding_profiles.py','test_dawnfall_draw_profiles.py','test_dawnfall_action_profiles.py','test_cosmetic_action_profiles.py','test_placement_art.py','test_scoped_descriptions.py','test_checked_placement.py')) {
            & $python -m unittest discover -s tests -p $test -q *> (Join-Path $out "$test.log")
            if ($LASTEXITCODE -ne 0) {
                Get-Content (Join-Path $out "$test.log")
                throw "Three-build lifecycle verification failed: $test"
            }
        }
    } finally {
        $env:MAJESTY_REQUIRE_DAMAGE_FIXTURES = $previousDamageFixtures
        Pop-Location
    }
}
