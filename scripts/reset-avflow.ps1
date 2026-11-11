# reset-avflow.ps1 — remove avflow (and the older kickoff-kit / htkm-kit / redmine-agent installs) from this
# Windows PC, so that the next install behaves like a first install.
#
# Keeps: git, uv, gh, glab, Claude Code, and your GitHub / GitLab logins (unless -LogoutGitLab).
# Usage (PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\reset-avflow.ps1
#   ... -Yes                          no confirmation
#   ... -KeepSuperpowers              keep the Superpowers plugin
#   ... -LogoutGitLab gitlab.enclave.vn
param([switch]$Yes, [switch]$KeepSuperpowers, [string]$LogoutGitLab = "")

if (-not $Yes) {
  $a = Read-Host "This removes avflow, its token, plugin, MCP server, skills and settings entries. Continue? [y/N]"
  if ($a -notin @("y", "Y")) { Write-Host "Cancelled."; exit 0 }
}

function Step($t) { Write-Host "`n== $t" }
function Quiet([scriptblock]$b) { try { & $b *> $null } catch { } }
function Has($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

$H = $env:USERPROFILE
$C = Join-Path $H ".claude"

Step "avflow's own uninstall"
if (Has "avflow") { Quiet { avflow uninstall } }
if (Has "kickoff-kit") { Quiet { kickoff-kit uninstall } }
if (Has "htkm-kit")    { Quiet { htkm-kit uninstall } }

Step "Command-line tools (uv)"
foreach ($t in "avflow", "kickoff-kit", "htkm-kit", "redmine-agent-mcp") { Quiet { uv tool uninstall $t } }

Step "Claude Code plugins and marketplaces"
Quiet { claude plugin uninstall avflow@avflow }
Quiet { claude plugin uninstall kickoff-kit@kickoff-kit }
Quiet { claude plugin uninstall htkm-kit@htkm-kit }
Quiet { claude plugin marketplace remove avflow }
Quiet { claude plugin marketplace remove kickoff-kit }
Quiet { claude plugin marketplace remove htkm-kit }
if (-not $KeepSuperpowers) {
  Quiet { claude plugin uninstall superpowers@superpowers-marketplace }
  Quiet { claude plugin marketplace remove superpowers-marketplace }
}

Step "Claude Code MCP servers"
foreach ($m in "avflow-tickets", "kickoff-tickets", "htkm-tickets", "redmine-agent") { Quiet { claude mcp remove $m --scope user } }

Step "Skills, configuration and caches"
$paths = @(
  "$C\agents\avflow-planner.md", "$C\agents\avflow-implementer.md", "$C\agents\avflow-reviewer.md",
  "$C\skills\handoff", "$C\skills\zoom-out", "$C\skills\grill-with-docs", "$C\skills\implement", "$C\skills\tdd",
  "$C\skills\diagnosing-bugs", "$C\skills\code-review", "$C\skills\prototype", "$C\skills\research",
  "$C\skills\codebase-design", "$C\skills\improve-codebase-architecture", "$C\skills\pr", "$C\skills\retro",
  "$H\.avflow", "$H\.kickoff-kit", "$H\.htkm-kit", "$H\.redmine-agent-mcp",
  "$C\plugins\cache\avflow", "$C\plugins\marketplaces\avflow",
  "$C\plugins\cache\kickoff-kit", "$C\plugins\marketplaces\kickoff-kit",
  "$C\plugins\cache\htkm-kit", "$C\plugins\marketplaces\htkm-kit"
)
if (-not $KeepSuperpowers) {
  $paths += "$C\plugins\cache\superpowers-marketplace", "$C\plugins\marketplaces\superpowers-marketplace"
}
foreach ($p in $paths) { if (Test-Path $p) { Remove-Item -Recurse -Force $p } }

Step "Permission and hook entries in .claude\settings.json"
$sf = "$C\settings.json"
if (Test-Path $sf) {
  try {
    $d = Get-Content $sf -Raw | ConvertFrom-Json
    if ($d.hooks) {
      foreach ($ev in @($d.hooks.PSObject.Properties.Name)) {
        $kept = @()
        foreach ($e in $d.hooks.$ev) {
          $hs = @($e.hooks | Where-Object { "$($_.command)" -notmatch '(avflow|kickoff)-git-guard|avflow-monitor' })
          if ($hs.Count -gt 0) { $e.hooks = $hs; $kept += $e }
        }
        if ($kept.Count -gt 0) { $d.hooks.$ev = $kept } else { $d.hooks.PSObject.Properties.Remove($ev) }
      }
      if (@($d.hooks.PSObject.Properties).Count -eq 0) { $d.PSObject.Properties.Remove('hooks') }
    }
    if ($d.permissions) {
      foreach ($k in "allow", "ask", "deny") {
        if ($d.permissions.$k) {
          $d.permissions.$k = @($d.permissions.$k | Where-Object { $_ -notmatch '^mcp__(avflow-tickets|kickoff-tickets|htkm-tickets|redmine-agent)__' })
        }
      }
      $d | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $sf
    }
    Write-Host "cleaned"
  } catch { Write-Host "settings.json is not valid JSON — left unchanged" }
} else { Write-Host "no settings.json" }
foreach ($b in "$sf.avflow-backup", "$sf.kickoff-backup", "$sf.htkm-backup") { if (Test-Path $b) { Remove-Item -Force $b } }

Step "Credential Manager entries"
$targets = (cmdkey /list) | Where-Object { $_ -match "Target:" -and $_ -match "(avflow|kickoff-kit|htkm-kit)" } |
  ForEach-Object { ($_ -split "Target:\s*", 2)[1].Trim() -replace '^LegacyGeneric:target=', '' }
foreach ($t in $targets) { cmdkey /delete:$t | Out-Null; Write-Host "removed: $t" }
if (-not $targets) { Write-Host "none found" }

if ($LogoutGitLab) {
  Step "GitLab sign-out ($LogoutGitLab)"
  Quiet { glab auth logout --hostname $LogoutGitLab }
}

Step "Check"
$fail = $false
foreach ($c in "avflow", "kickoff-kit", "htkm-kit", "redmine-agent-mcp") { if (Has $c) { Write-Host "  still present: $c"; $fail = $true } }
try { if ((claude mcp list 2>$null) -match "avflow-tickets|kickoff-tickets|htkm-tickets|redmine-agent") { Write-Host "  MCP server still registered"; $fail = $true } } catch { }
try { if ((claude plugin list 2>$null) -match "avflow|kickoff-kit|htkm-kit") { Write-Host "  plugin still installed (remove it with /plugin in Claude Code)"; $fail = $true } } catch { }
if (Test-Path "$C\skills\handoff") { Write-Host "  skill handoff still present"; $fail = $true }
if (-not $fail) { Write-Host "  ✅ Clean — ready for a first install." } else { Write-Host "  ❌ Some items remain (see above)." }
Write-Host "`nRestart Claude Code before installing again."
