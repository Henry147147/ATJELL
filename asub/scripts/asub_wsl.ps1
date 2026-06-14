param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AsubArgs
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRootForWslPath = $RepoRoot -replace "\\", "/"
$WslRoot = (& wsl.exe wslpath -a $RepoRootForWslPath).Trim()
if (-not $WslRoot) {
    throw "Could not resolve the repository path inside WSL."
}

& wsl.exe --cd $WslRoot bash -lc 'source .asub-env && exec asub "$@"' asub @AsubArgs
exit $LASTEXITCODE
