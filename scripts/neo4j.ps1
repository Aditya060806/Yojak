<#
.SYNOPSIS
  Project-local Neo4j Community (no Docker, no system install).

.EXAMPLE
  scripts/neo4j.ps1 install   # download + configure into tools/neo4j (needs Java 17+)
  scripts/neo4j.ps1 start     # start in the background, wait until Bolt is up
  scripts/neo4j.ps1 stop
  scripts/neo4j.ps1 status
#>
param([ValidateSet("install", "start", "stop", "status")][string]$Action = "status")

# Native tools (npm, java, pip) write warnings to stderr; with "Stop", Windows
# PowerShell 5.1 would turn those into fatal errors. Failures are checked via
# $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Version = "5.26.31"
$Tools = Join-Path $Root "tools"
$Home4j = Join-Path $Tools "neo4j"
$EnvFile = Join-Path $Root ".env"

function Get-EnvValue([string]$Name) {
    if (-not (Test-Path $EnvFile)) { return $null }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim().Trim('"') }
    return $null
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

switch ($Action) {
    "install" {
        if (Test-Path (Join-Path $Home4j "bin\neo4j.bat")) { Write-Host "Neo4j already installed at $Home4j"; break }
        if (-not (Get-Command java -ErrorAction SilentlyContinue)) { throw "Java 17+ is required (e.g. Eclipse Temurin 17)." }
        New-Item -ItemType Directory -Force $Tools | Out-Null
        $zip = Join-Path $Tools "neo4j.zip"
        $url = "https://dist.neo4j.org/neo4j-community-$Version-windows.zip"
        Write-Host "Downloading $url"
        Invoke-WebRequest $url -OutFile $zip
        $expected = (Invoke-WebRequest "$url.sha256").Content.ToString().Trim().Substring(0, 64)
        $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expected.ToLower()) { throw "Checksum mismatch for $zip" }
        Expand-Archive $zip -DestinationPath $Tools -Force
        Rename-Item (Join-Path $Tools "neo4j-community-$Version") $Home4j
        Add-Content (Join-Path $Home4j "conf\neo4j.conf") "`nserver.memory.heap.initial_size=1g`nserver.memory.heap.max_size=2g`nserver.memory.pagecache.size=1g"
        $pw = Get-EnvValue "NEO4J_PASSWORD"
        if (-not $pw -or $pw -eq "change-me") { throw "Set NEO4J_PASSWORD in .env first (scripts/setup.ps1 does this)." }
        & (Join-Path $Home4j "bin\neo4j-admin.bat") dbms set-initial-password $pw | Out-Null
        Write-Host "Neo4j $Version installed. Password taken from .env."
    }
    "start" {
        if (Test-Port 7687) { Write-Host "Neo4j already running (bolt://127.0.0.1:7687)"; break }
        $bat = Join-Path $Home4j "bin\neo4j.bat"
        if (-not (Test-Path $bat)) { throw "Neo4j not installed. Run: scripts/neo4j.ps1 install" }
        New-Item -ItemType Directory -Force (Join-Path $Home4j "logs") | Out-Null
        $log = Join-Path $Home4j "logs\console.log"
        # cmd /c strips one pair of outer quotes, so the whole command is wrapped once more.
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"`"$bat`" console > `"$log`" 2>&1`"" -WindowStyle Hidden
        for ($i = 0; $i -lt 60; $i++) { if (Test-Port 7687) { break }; Start-Sleep 2 }
        if (-not (Test-Port 7687)) { throw "Neo4j did not start; see $log" }
        Write-Host "Neo4j running: bolt://127.0.0.1:7687  browser: http://127.0.0.1:7474"
    }
    "stop" {
        $conn = Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue
        if (-not $conn) { Write-Host "Neo4j is not running"; break }
        Stop-Process -Id $conn.OwningProcess -Force
        Write-Host "Neo4j stopped"
    }
    "status" {
        if (Test-Port 7687) { Write-Host "running" } else { Write-Host "stopped" }
    }
}
