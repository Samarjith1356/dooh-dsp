# Sets up the Cursor connector for Claude on this PC. Safe to run more than once.
#   1. Installs the Cursor CLI if it is missing
#   2. Turns on the repo's commit hook and keeps job folders out of git
#   3. Removes the old connector entry from earlier attempts (the extension replaces it)
#   4. Logs the Cursor CLI in (opens your browser)
#   5. Opens Claude's installer for the cursor-bridge extension
# Run by double-clicking setup.cmd, or from PowerShell:
#   powershell -ExecutionPolicy Bypass -File "$HOME\dooh-dsp\tools\cursor-bridge\setup.ps1"

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$mcpb = Join-Path $PSScriptRoot 'cursor-bridge.mcpb'
$logDir = Join-Path $repo '.cursor-bridge'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir 'setup-log.txt') -Force | Out-Null
Write-Host ""
Write-Host "== Cursor connector setup ==" -ForegroundColor Cyan
Write-Host "Repo: $repo"

function Find-Agent {
    foreach ($n in 'agent', 'cursor-agent') {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c -and $c.Source) { return $c.Source }
    }
    $dir = Join-Path $env:LOCALAPPDATA 'cursor-agent'
    foreach ($f in 'agent.cmd', 'agent.exe', 'agent.ps1', 'cursor-agent.cmd', 'cursor-agent.exe', 'cursor-agent.ps1') {
        $p = Join-Path $dir $f
        if (Test-Path $p) { return $p }
    }
    return $null
}

# 1. Cursor CLI
Write-Host ""
Write-Host "[1/5] Cursor CLI" -ForegroundColor Cyan
$agent = Find-Agent
if (-not $agent) {
    Write-Host "Installing Cursor CLI from cursor.com ..."
    Invoke-RestMethod 'https://cursor.com/install?win32=true' | Invoke-Expression
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $agent = Find-Agent
}
if (-not $agent) { throw "Cursor CLI still not found. Close PowerShell, open a new one and run this script again." }
Write-Host "Found: $agent"

# 2. Git settings for this repo
Write-Host ""
Write-Host "[2/5] Git settings" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found. Install Git for Windows and run this script again." }
git -C $repo config core.hooksPath .githooks
$exclude = Join-Path $repo '.git\info\exclude'
$current = ''
if (Test-Path $exclude) { $current = Get-Content $exclude -Raw }
foreach ($pattern in '.cursor-bridge/', '.bridge-prompt.md') {
    if ($current -notmatch [regex]::Escape($pattern)) { Add-Content -Path $exclude -Value $pattern }
}
Write-Host "Commit hook on, local job folders ignored."

# 3. Remove the old connector entry (now replaced by the extension)
Write-Host ""
Write-Host "[3/5] Tidy old connector config" -ForegroundColor Cyan
$utf8 = New-Object System.Text.UTF8Encoding($false)
$targets = @(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')
$pkgRoot = Join-Path $env:LOCALAPPDATA 'Packages'
if (Test-Path $pkgRoot) {
    Get-ChildItem $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue | ForEach-Object {
        $targets += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')
    }
}
foreach ($t in $targets) {
    if (-not (Test-Path $t)) { continue }
    try {
        $cfg = Get-Content $t -Raw | ConvertFrom-Json
        if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'mcpServers') -and ($cfg.mcpServers.PSObject.Properties.Name -contains 'cursor-bridge')) {
            Copy-Item $t ("$t.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
            $cfg.mcpServers.PSObject.Properties.Remove('cursor-bridge')
            [System.IO.File]::WriteAllText($t, ($cfg | ConvertTo-Json -Depth 32), $utf8)
            Write-Host "Removed old entry from: $t"
        } else { Write-Host "Nothing to remove in: $t" }
    } catch { Write-Host "Skipped (could not read): $t  $_" }
}

# 4. Cursor login
Write-Host ""
Write-Host "[4/5] Cursor login" -ForegroundColor Cyan
$ErrorActionPreference = 'Continue'   # native tools write progress to stderr; don't treat it as a failure
$status = (& $agent status 2>&1 | Out-String)
Write-Host $status.Trim()
$loggedIn = ($status -match '(?i)(logged in|authenticated|signed in)') -and ($status -notmatch '(?i)\bnot (logged|authenticated|signed)')
if (-not $loggedIn) {
    Write-Host "Opening your browser to log the Cursor CLI in. Approve it with your Cursor account." -ForegroundColor Yellow
    & $agent login
    $status = (& $agent status 2>&1 | Out-String)
    Write-Host $status.Trim()
    $loggedIn = ($status -match '(?i)(logged in|authenticated|signed in)') -and ($status -notmatch '(?i)\bnot (logged|authenticated|signed)')
}
if ($loggedIn) { Write-Host "Cursor CLI is logged in." -ForegroundColor Green }
else { Write-Host "Cursor CLI is still not logged in. Run this script again after approving in the browser." -ForegroundColor Yellow }

# 5. Install the extension into Claude
Write-Host ""
Write-Host "[5/5] Claude extension" -ForegroundColor Cyan
if (Test-Path $mcpb) {
    Write-Host "Opening Claude's installer for: $mcpb"
    try {
        Start-Process $mcpb
        Write-Host "In Claude: click Install, check the repo folder is $repo, then make sure the extension is switched on." -ForegroundColor Green
    } catch {
        Write-Host "Could not open it automatically. In Claude go to Settings > Extensions > Advanced settings > Install Extension, and pick:" -ForegroundColor Yellow
        Write-Host "  $mcpb"
    }
} else {
    Write-Host "cursor-bridge.mcpb not found next to this script. Run 'git pull' in $repo and try again." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Done. Go back to the chat and say: extension installed." -ForegroundColor Green
Stop-Transcript | Out-Null
