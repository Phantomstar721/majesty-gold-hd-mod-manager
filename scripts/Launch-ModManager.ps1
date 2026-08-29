param()

$ErrorActionPreference = "Stop"
try {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $pythonw = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
        throw "The manager environment was not found. Run Setup - Majesty Mod Manager.bat first."
    }

    # Setup installs this checkout editable into the private environment, so the
    # elevated child does not depend on a transient PYTHONPATH crossing UAC.
    Start-Process -FilePath $pythonw `
        -ArgumentList @("-m", "majesty_cam.manager.app") `
        -WorkingDirectory $repoRoot `
        -Verb RunAs `
        -WindowStyle Hidden
}
catch {
    $detail = $_.Exception.Message
    try {
        $shell = New-Object -ComObject WScript.Shell
        [void]$shell.Popup(
            "Majesty Mod Manager could not start.`r`n`r`n$detail",
            0,
            "Majesty Mod Manager",
            16
        )
    }
    catch {
        # Preserve the nonzero result even if Windows cannot show the dialog.
    }
    Write-Error $detail
    exit 1
}
