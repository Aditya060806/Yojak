<#
.SYNOPSIS
  One-time local setup for Yojak (Windows, no Docker).

  Creates .venv, installs Python and frontend dependencies, writes .env with a
  random Neo4j password, and installs a project-local Neo4j.

.PARAMETER Torch
  cuda (default when nvidia-smi exists), cpu, or skip (keep whatever torch is importable).
#>
param([ValidateSet("auto", "cuda", "cpu", "skip")][string]$Torch = "auto")

# Native tools (npm, java, pip) write warnings to stderr; with "Stop", Windows
# PowerShell 5.1 would turn those into fatal errors. Failures are checked via
# $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

# 1) .env with a random Neo4j password
if (-not (Test-Path ".env")) {
    $pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    (Get-Content ".env.example") -replace "^NEO4J_PASSWORD=.*", "NEO4J_PASSWORD=$pw" | Set-Content ".env" -Encoding utf8
    Write-Host "Created .env"
}

# 2) Python venv
if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = Join-Path $Root ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip -q

if ($Torch -eq "auto") { $Torch = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "cuda" } else { "cpu" } }
switch ($Torch) {
    "cuda" { & $py -m pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121 }
    "cpu"  { & $py -m pip install -q torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu }
    "skip" { }
}
& $py -m pip install -q -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "Python dependencies installed"

# 3) Frontend
Push-Location "app/frontend"
npm ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm ci failed" }
if (-not (Test-Path ".env.local")) { "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" | Set-Content ".env.local" -Encoding utf8 }
Pop-Location
Write-Host "Frontend dependencies installed"

# 4) Data folders + Neo4j
"data/raw/esco", "data/raw/naukri", "data/raw/external", "data/processed", "artifacts" |
    ForEach-Object { New-Item -ItemType Directory -Force $_ | Out-Null }
& (Join-Path $PSScriptRoot "neo4j.ps1") install

Write-Host ""
Write-Host "Setup done. Next:"
Write-Host "  1. Put the ESCO v1.2 English CSVs in data/raw/esco (manual download from esco.ec.europa.eu)"
Write-Host "  2. scripts/run.ps1 data       # Kaggle + public reference data (needs ~/.kaggle/kaggle.json)"
Write-Host "  3. scripts/run.ps1 pipeline   # build graph, indexes, models and reports"
Write-Host "  4. scripts/run.ps1 up         # Neo4j + API + web on http://localhost:3000"
