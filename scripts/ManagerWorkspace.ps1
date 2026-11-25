function Resolve-WorkspaceRepo([string]$WorkspaceRoot, [string]$Group, [string]$Name) {
    $grouped = Join-Path $WorkspaceRoot "$Group\$Name"
    $current = Join-Path $WorkspaceRoot $Name
    if ((Test-Path -LiteralPath $grouped) -or -not (Test-Path -LiteralPath $current -PathType Container)) {
        return $grouped
    }
    return $current
}
