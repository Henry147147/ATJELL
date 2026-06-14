param(
    [switch]$Force,
    [switch]$WithGui,
    [switch]$NoFlashAttn
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RepoRootForWslPath = $RepoRoot -replace "\\", "/"
$WslRoot = (& wsl.exe wslpath -a $RepoRootForWslPath).Trim()
if (-not $WslRoot) {
    throw "Could not resolve the repository path inside WSL."
}

$SetupArgs = @()
if ($Force) {
    $SetupArgs += "--force"
}
if ($WithGui) {
    $SetupArgs += "--with-gui"
}
if (-not $NoFlashAttn) {
    $SetupArgs += "--flash-attn"
}

Write-Host "Setting up asub under WSL at $WslRoot"
& wsl.exe --cd $WslRoot bash scripts/setup_linux_venvs.sh @SetupArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Setup complete. From PowerShell, run:"
Write-Host "  .\scripts\asub_wsl.ps1 doctor"
Write-Host "  .\scripts\asub_wsl.ps1 process `"/mnt/z/C/path/to/video.mp4`" --targets en --align"
