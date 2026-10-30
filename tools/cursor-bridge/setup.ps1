# Sets up the Cursor connector (cursor-bridge) for Claude on this PC.
# Safe to run more than once. Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File "$HOME\dooh-dsp\tools\cursor-bridge\setup.ps1"

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$bridge = Join-Path $PSScriptRoot 'cursor_bridge.py'
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
$utf8 = New-Object System.Text.UTF8Encoding($false)
$realCfg = Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'
$targets = @($realCfg)
$pkgRoot = Join-Path $env:LOCALAPPDATA 'Packages'
if (Test-Path $pkgRoot) {
    Get-ChildItem $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue | ForEach-Object {
        $targets += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')
    }
}
# Start from whichever existing config has the most servers, so nothing already set up is lost
$base = '{}'
$bestCount = -1
foreach ($t in $targets) {
    if (Test-Path $t) {
        $raw = Get-Content $t -Raw
        Write-Host "Found config: $t"
        try {
            $obj = $raw | ConvertFrom-Json
            $n = 0
            if ($obj.PSObject.Properties.Name -contains 'mcpServers') { $n = @($obj.mcpServers.PSObject.Properties).Count }
            Write-Host ("  servers: " + (($obj.mcpServers.PSObject.Properties.Name) -join ', '))
            if ($n -gt $bestCount) { $bestCount = $n; $base = $raw }
        } catch { Write-Host "  (could not parse this file: $_)" }
    } else { Write-Host "No config yet at: $t" }
}
if ([string]::IsNullOrWhiteSpace($base)) { $base = '{}' }
$cfg = $base | ConvertFrom-Json
if (-not $cfg) { $cfg = [pscustomobject]@{} }
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
foreach ($t in $targets) {
    New-Item -ItemType Directory -Force -Path (Split-Path $t) | Out-Null
    if (Test-Path $t) { Copy-Item $t ("$t.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
    [System.IO.File]::WriteAllText($t, $json, $utf8)
    Write-Host "Wrote: $t"
}
Write-Host ("Servers now configured: " + (($cfg.mcpServers.PSObject.Properties.Name) -join ', '))

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
Write-Host "[done] Restarting Claude so it loads the connector..." -ForegroundColor Cyan
$claudeProcs = Get-Process -Name 'Claude' -ErrorAction SilentlyContinue
$claudeExe = $null
if ($claudeProcs) { $claudeExe = ($claudeProcs | Where-Object { $_.Path } | Select-Object -First 1).Path }
$pkg = Get-AppxPackage -Name 'Claude*' -ErrorAction SilentlyContinue | Select-Object -First 1
Write-Host "Claude processes: $(@($claudeProcs).Count)  exe: $claudeExe  store package: $($pkg.PackageFamilyName)"
if ($claudeProcs) { $claudeProcs | Stop-Process -Force; Start-Sleep -Seconds 3 }
$started = $false
if ($pkg) {
    try {
        $appId = (Get-AppxPackageManifest $pkg).Package.Applications.Application | Select-Object -First 1 -ExpandProperty Id
        Start-Process ("shell:AppsFolder\" + $pkg.PackageFamilyName + "!" + $appId)
        $started = $true
    } catch { Write-Host "Could not start the Store app: $_" }
}
if (-not $started -and $claudeExe) { Start-Process $claudeExe; $started = $true }
if ($started) { Write-Host "Claude restarted." -ForegroundColor Green } else { Write-Host "Please open Claude again yourself." -ForegroundColor Yellow }
Write-Host ""
Write-Host "Done. Go back to the chat and say: connector ready." -ForegroundColor Green
Stop-Transcript | Out-Null
