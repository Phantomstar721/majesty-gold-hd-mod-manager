param(
    [string]$ApplicationRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $repoRoot "dist"
if (-not $ApplicationRoot) {
    $ApplicationRoot = Join-Path $distRoot "Majesty Mod Manager"
}
$applicationRoot = [IO.Path]::GetFullPath($ApplicationRoot)
$target = Join-Path $distRoot "workshop-upload"
$stage = Join-Path $distRoot (".workshop-upload-stage-" + [guid]::NewGuid().ToString("N"))
$backup = Join-Path $distRoot (".workshop-upload-backup-" + [guid]::NewGuid().ToString("N"))
$ownershipMarker = ".majesty-mod-manager-workshop-stage"
$projectName = "MajestyModManager.mswproj"
$projectSource = Join-Path $repoRoot ("workshop\" + $projectName)
$previewSource = Join-Path $repoRoot "workshop\workshop-preview.jpg"
$instructionsSource = Join-Path $repoRoot "workshop\START HERE.txt"
$licenseRoot = Join-Path $repoRoot "licenses"

$required = @(
    (Join-Path $applicationRoot "Majesty Mod Manager.exe"),
    (Join-Path $applicationRoot "_internal\payload\runtime\MajestyBuildingRuntimeLauncher.exe"),
    (Join-Path $applicationRoot "_internal\payload\runtime\MajestyBuildingRuntime.dll"),
    (Join-Path $applicationRoot "_internal\profiles\manager\compatibility.json"),
    $projectSource,
    $previewSource,
    $instructionsSource,
    (Join-Path $repoRoot "LICENSE"),
    (Join-Path $repoRoot "THIRD-PARTY-NOTICES.md"),
    (Join-Path $licenseRoot "PYTHON-3.9.txt"),
    (Join-Path $licenseRoot "LGPL-3.0.txt"),
    (Join-Path $licenseRoot "GPL-3.0.txt"),
    (Join-Path $licenseRoot "PYINSTALLER.txt"),
    (Join-Path $repoRoot "src\majesty_cam\manager\assets\STEAM-ICON-NOTICE.txt")
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required Workshop input is missing: $path"
    }
}

$reparseInput = Get-ChildItem -LiteralPath $applicationRoot -Recurse -Force |
    Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 } |
    Select-Object -First 1
if ($null -ne $reparseInput) {
    throw "Refusing to stage an application containing a link or reparse point: $($reparseInput.FullName)"
}

if (Test-Path -LiteralPath $target) {
    $targetItem = Get-Item -LiteralPath $target -Force
    if (($targetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to replace a linked Workshop staging directory: $target"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $target $ownershipMarker) -PathType Leaf)) {
        throw "Refusing to replace a Workshop directory not owned by Majesty Mod Manager: $target"
    }
}

try {
    $contentPath = Join-Path $stage "content"
    $stagedLicenses = Join-Path $contentPath "licenses"
    New-Item -ItemType Directory -Path $contentPath -Force | Out-Null
    New-Item -ItemType Directory -Path $stagedLicenses -Force | Out-Null

    Get-ChildItem -LiteralPath $applicationRoot -Force |
        Copy-Item -Destination $contentPath -Recurse -Force
    Copy-Item -LiteralPath $instructionsSource -Destination (Join-Path $contentPath "START HERE.txt") -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $contentPath "LICENSE.txt") -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "THIRD-PARTY-NOTICES.md") -Destination (Join-Path $contentPath "THIRD-PARTY-NOTICES.md") -Force
    Get-ChildItem -LiteralPath $licenseRoot -File -Force |
        Copy-Item -Destination $stagedLicenses -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "src\majesty_cam\manager\assets\STEAM-ICON-NOTICE.txt") -Destination (Join-Path $stagedLicenses "STEAM-ICON-NOTICE.txt") -Force
    Copy-Item -LiteralPath $previewSource -Destination (Join-Path $stage "workshop-preview.jpg") -Force

    $projectText = Get-Content -LiteralPath $projectSource -Raw
    $finalContentPath = [Security.SecurityElement]::Escape((Join-Path $target "content"))
    $finalPreviewPath = [Security.SecurityElement]::Escape((Join-Path $target "workshop-preview.jpg"))
    $projectText = [regex]::Replace(
        $projectText,
        '<ContentPath>.*?</ContentPath>',
        ('<ContentPath>' + $finalContentPath + '</ContentPath>')
    )
    $projectText = [regex]::Replace(
        $projectText,
        '<PreviewImagePath>.*?</PreviewImagePath>',
        ('<PreviewImagePath>' + $finalPreviewPath + '</PreviewImagePath>')
    )
    $existingProject = Join-Path $target $projectName
    if (Test-Path -LiteralPath $existingProject -PathType Leaf) {
        $existingText = Get-Content -LiteralPath $existingProject -Raw
        $existingId = [regex]::Match($existingText, '<SteamWorkshop id="([1-9][0-9]*)"')
        if ($existingId.Success) {
            $projectText = $projectText -replace '<SteamWorkshop id="[0-9]+"', ('<SteamWorkshop id="' + $existingId.Groups[1].Value + '"')
        }
    }
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText((Join-Path $stage $projectName), $projectText, $utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $stage $ownershipMarker), "schema=1`r`n", [Text.Encoding]::ASCII)

    $contentFiles = @(Get-ChildItem -LiteralPath $contentPath -Recurse -File -Force | Sort-Object FullName)
    if ($contentFiles.Count -lt 10) {
        throw "Workshop content is unexpectedly incomplete: $($contentFiles.Count) files"
    }
    $manifestLines = foreach ($file in $contentFiles) {
        $relative = $file.FullName.Substring($contentPath.Length).TrimStart('\').Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToUpperInvariant()
        "$hash  $relative"
    }
    [IO.File]::WriteAllText(
        (Join-Path $stage "SHA256.txt"),
        (($manifestLines -join "`r`n") + "`r`n"),
        [Text.Encoding]::ASCII
    )

    if (Test-Path -LiteralPath $target) {
        Move-Item -LiteralPath $target -Destination $backup
    }
    Move-Item -LiteralPath $stage -Destination $target
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
}
catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    throw
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}

$finalFiles = @(Get-ChildItem -LiteralPath (Join-Path $target "content") -Recurse -File -Force)
$totalBytes = ($finalFiles | Measure-Object -Property Length -Sum).Sum
$exeHash = (Get-FileHash -LiteralPath (Join-Path $target "content\Majesty Mod Manager.exe") -Algorithm SHA256).Hash.ToUpperInvariant()
Write-Host "Workshop upload staged: $target"
Write-Host "  Files:  $($finalFiles.Count)"
Write-Host "  Bytes:  $totalBytes"
Write-Host "  EXE SHA256: $exeHash"
Write-Host "  Project: $(Join-Path $target $projectName)"
