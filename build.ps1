param(
    [string]$ServerUrl = "ws://192.168.1.6:8000/ws/agent"
)

$ErrorActionPreference = "Stop"

$REQUIRED_VERSION = "3.9"
$PYTHON = "python"

function Get-PythonVersion {
    $ver = & $PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if (-not $ver) { return $null }
    return [version]$ver
}

$pyVer = Get-PythonVersion
if (-not $pyVer -or $pyVer -lt [version]$REQUIRED_VERSION) {
    Write-Host "ERROR: Python $REQUIRED_VERSION+ required (found $pyVer)" -ForegroundColor Red
    exit 1
}

Write-Host "Python $pyVer detected" -ForegroundColor Green

$pip = try { & $PYTHON -m pip --version 2>$null; $true } catch { $false }
if (-not $pip) {
    Write-Host "ERROR: pip not available" -ForegroundColor Red
    exit 1
}

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $PYTHON -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed" -ForegroundColor Red
    exit 1
}

$pyinstaller = try { & $PYTHON -m PyInstaller --version 2>$null; $true } catch { $false }
if (-not $pyinstaller) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    & $PYTHON -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: PyInstaller install failed" -ForegroundColor Red
        exit 1
    }
}

$clean = Read-Host "Clean previous build artifacts? (y/N)"
if ($clean -eq "y") {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "release") { Remove-Item -Recurse -Force "release" }
    if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }
}

Write-Host "Building honmonit-agent.exe ..." -ForegroundColor Yellow

$projectRoot = (Get-Item -Path ".").FullName

$pyinstallerArgs = @(
    "--onefile"
    "--noconsole"
    "--name", "honmonit-agent"
    "--add-data", "$projectRoot\agent;agent"
    "--hidden-import", "agent.identity"
    "--hidden-import", "psutil"
    "--hidden-import", "websockets"
    "--distpath", "release"
    "--workpath", "build/pyinstaller"
    "--specpath", "build"
    "--clean"
    "-y"
    "agent/agent.py"
)

& $PYTHON -m PyInstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    exit 1
}

$exePath = "release/honmonit-agent.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: $exePath not found after build" -ForegroundColor Red
    exit 1
}

Write-Host @"

Build successful!
  Output: $exePath
  Size:  $([math]::Round((Get-Item $exePath).Length / 1MB, 2)) MB

Creating config.json for release...
"@ -ForegroundColor Green

$config = @{
    server_url = $ServerUrl
} | ConvertTo-Json
Set-Content -Path "release/config.json" -Value $config

Write-Host @"

Release contents:
  release/honmonit-agent.exe   - Agent executable
  release/config.json          - Server configuration

Deploy by copying the release/ folder to target machines.
"@ -ForegroundColor Green
