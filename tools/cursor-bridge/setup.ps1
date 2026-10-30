# Sets up the Cursor connector (cursor-bridge) for Claude on this PC.
# Safe to run more than once. Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File "$HOME\dooh-dsp\tools\cursor-bridge\setup.ps1"

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$bridge = Join-Path $PSScriptRoot 'cursor_bridge.py'
Write-Host ""
Write-Host "== Cursor connector setup ==" -ForegroundColor Cyan
Write-Host "Repo: $repo"

function Find-Agent {
    foreach ($n in 'agent', 'cursor-agent') {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c -and $c.Source) { return $c.Source }
    }
    $dir = Join-Path $env:LOCALAPPDATA 'cursor-agent'
    foreach ($f in 'agent.cmd', 'agent.exe', 'cursor-agent.cmd', 'cursor-agent.exe') {
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

# 2. Python
Write-Host ""
Write-Host "[2/5] Python" -ForegroundColor Cyan
$python = $null
foreach ($c in @((Join-Path $env:USERPROFILE 'anaconda3\python.exe'), (Join-Path $env:USERPROFILE 'miniconda3\python.exe'))) {
    if (Test-Path $c) { $python = $c; break }
}
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notmatch 'WindowsApps') { $python = $cmd.Source }
}
if (-not $python) {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { $python = (& py -3 -c "import sys; print(sys.executable)").Trim() }
}
if (-not $python) { throw "Python 3 not found. Install it from python.org and run this script again." }
Write-Host "Found: $python"

# 3. Git settings for this repo
Write-Host ""
Write-Host "[3/5] Git settings" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found. Install Git for Windows and run this script again." }
git -C $repo config core.hooksPath .githooks
$exclude = Join-Path $repo '.git\info\exclude'
$current = ''
if (Test-Path $exclude) { $current = Get-Content $exclude -Raw }
foreach ($pattern in '.cursor-bridge/', '.bridge-prompt.md') {
    if ($current -notmatch [regex]::Escape($pattern)) { Add-Content -Path $exclude -Value $pattern }
}
Write-Host "Commit hook enabled, local job folders ignored."

# 4. Register with the Claude desktop app
Write-Host ""
Write-Host "[4/5] Claude desktop config" -ForegroundColor Cyan
$candidates = @(Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')
$pkgRoot = Join-Path $env:LOCALAPPDATA 'Packages'
if (Test-Path $pkgRoot) {
    Get-ChildItem $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')
    }
}
$targets = @($candidates | Where-Object { Test-Path $_ })
if ($targets.Count -eq 0) {
    $targets = @($candidates[0])
    New-Item -ItemType Directory -Force -Path (Split-Path $targets[0]) | Out-Null
    [System.IO.File]::WriteAllText($targets[0], '{}', (New-Object System.Text.UTF8Encoding($false)))
}
foreach ($cfgPath in $targets) {
    Copy-Item $cfgPath ("$cfgPath.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $raw = Get-Content $cfgPath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = '{}' }
    $cfg = $raw | ConvertFrom-Json
    if (-not ($cfg.PSObject.Properties.Name -contains 'mcpServers')) {
        $cfg | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue ([pscustomobject]@{})
    }
    $entry = [pscustomobject]@{
        command = $python
        args    = @($bridge)
        env     = [pscustomobject]@{ DOOH_REPO = $repo; CURSOR_AGENT_PATH = $agent }
    }
    $cfg.mcpServers | Add-Member -NotePropertyName 'cursor-bridge' -NotePropertyValue $entry -Force
    $json = $cfg | ConvertTo-Json -Depth 32
    [System.IO.File]::WriteAllText($cfgPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Updated: $cfgPath (backup saved next to it)"
}

# 5. Cursor login and health check
Write-Host ""
Write-Host "[5/5] Cursor login" -ForegroundColor Cyan
$ErrorActionPreference = 'Continue'   # native tools write progress to stderr; don't treat it as a failure
$status = (& $agent status 2>&1 | Out-String)
Write-Host $status.Trim()
if ($status -notmatch '(?i)logged in|authenticated as|signed in') {
    Write-Host "Opening the browser to log the Cursor CLI in. Approve it with your Cursor account." -ForegroundColor Yellow
    & $agent login
}
Write-Host ""
Write-Host "Health check:" -ForegroundColor Cyan
$env:DOOH_REPO = $repo
$env:CURSOR_AGENT_PATH = $agent
& $python $bridge --self-test

Write-Host ""
Write-Host "Done. Now fully quit Claude (right-click its tray icon > Quit) and open it again." -ForegroundColor Green
Write-Host "Then go back to the chat and say: connector ready." -ForegroundColor Green
