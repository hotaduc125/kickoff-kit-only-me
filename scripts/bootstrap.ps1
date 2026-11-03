# kickoff-kit bootstrap (Windows PowerShell): installs uv if needed, installs kickoff-kit, runs setup.
# Usage: .\bootstrap.ps1 <wheel file | package spec>
param([string]$Source = "kickoff-kit")
$ErrorActionPreference = "Stop"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "Installing uv..."
  if (Get-Command winget -ErrorAction SilentlyContinue) { winget install --id astral-sh.uv -e --silent }
  else { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" }
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
uv tool install --force $Source
uv tool update-shell | Out-Null
& "$env:USERPROFILE\.local\bin\kickoff-kit.exe" setup
