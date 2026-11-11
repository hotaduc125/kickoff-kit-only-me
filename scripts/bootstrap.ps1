# avflow bootstrap (Windows PowerShell): installs uv if needed, installs avflow, runs setup.
# Usage:  powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-<version>-py3-none-any.whl
param([Parameter(Mandatory = $true)][string]$Source)
$ErrorActionPreference = "Stop"

function Add-ToPath([string]$dir) {
  if ((Test-Path $dir) -and -not (($env:Path -split ";") -contains $dir)) { $env:Path = "$dir;$env:Path" }
}

# uv may already be installed but not yet on this session's PATH
Add-ToPath "$env:USERPROFILE\.local\bin"
Add-ToPath "$env:LOCALAPPDATA\Microsoft\WinGet\Links"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "Installing uv..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id astral-sh.uv -e --silent --accept-source-agreements --accept-package-agreements
    Add-ToPath "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
  }
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Add-ToPath "$env:USERPROFILE\.local\bin"
  }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "uv could not be found after installing. Open a new PowerShell window and run this script again."
  exit 1
}

uv tool install --force $Source
uv tool update-shell | Out-Null
Add-ToPath "$env:USERPROFILE\.local\bin"

$kit = "$env:USERPROFILE\.local\bin\avflow.exe"
if (-not (Test-Path $kit)) { $kit = (Get-Command avflow -ErrorAction SilentlyContinue).Source }
if (-not $kit) { Write-Host "avflow was installed but not found. Open a new PowerShell window and run: avflow setup"; exit 1 }
& $kit setup
