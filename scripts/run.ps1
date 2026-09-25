<#
.SYNOPSIS
  Yojak task runner (Windows, no Docker).

.EXAMPLE
  scripts/run.ps1 up          # Neo4j + API (:8000) + web (:3000)
  scripts/run.ps1 api         # API only, foreground
  scripts/run.ps1 web         # production build + next start, foreground
  scripts/run.ps1 dev         # next dev, foreground
  scripts/run.ps1 data        # download Kaggle + public reference data
  scripts/run.ps1 pipeline    # build graph, indexes, models and reports
  scripts/run.ps1 eval        # run every evaluation, regenerate EVALUATION.md + README results
  scripts/run.ps1 demo        # three personas end to end -> reports/demo_output/
  scripts/run.ps1 test        # pytest + ruff + frontend typecheck/lint
  scripts/run.ps1 stop        # stop API, web and Neo4j
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "api", "web", "dev", "pipeline", "data", "eval", "demo", "test", "stop")]
    [string]$Task = "up",
    [Parameter(ValueFromRemainingArguments = $true)] [string[]]$Rest
)

# Native tools (npm, java, pip) write warnings to stderr; with "Stop", Windows
# PowerShell 5.1 would turn those into fatal errors. Failures are checked via
# $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run scripts/setup.ps1 first." }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONWARNINGS = "ignore"

function Stop-Port([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

function Wait-Port([int]$Port, [int]$Seconds = 120) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { return $true }
        Start-Sleep 1
    }
    return $false
}

switch ($Task) {
    "up" {
        & (Join-Path $PSScriptRoot "neo4j.ps1") start
        New-Item -ItemType Directory -Force "artifacts/logs" | Out-Null
        Stop-Port 8000
        Start-Process -FilePath $py -ArgumentList "-m uvicorn app.api.main:app --port 8000" `
            -RedirectStandardOutput "artifacts/logs/api.out.log" -RedirectStandardError "artifacts/logs/api.err.log" -WindowStyle Hidden
        if (-not (Wait-Port 8000)) { throw "API did not start; see artifacts/logs/api.err.log" }
        Write-Host "API running: http://127.0.0.1:8000/docs"
        Push-Location "app/frontend"
        if (-not (Test-Path ".next/BUILD_ID")) {
            npm run build
            if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend build failed" }
        }
        Pop-Location
        Stop-Port 3000
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run start > ..\..\artifacts\logs\web.log 2>&1" `
            -WorkingDirectory (Join-Path $Root "app/frontend") -WindowStyle Hidden
        if (-not (Wait-Port 3000)) { throw "Web app did not start; see artifacts/logs/web.log" }
        Write-Host "Web running: http://localhost:3000"
    }
    "api" { & $py -m uvicorn app.api.main:app --port 8000 --reload }
    "web" {
        Push-Location "app/frontend"
        npm run build
        if ($LASTEXITCODE -eq 0) { npm run start }
        Pop-Location
    }
    "dev" { Push-Location "app/frontend"; npm run dev; Pop-Location }
    "pipeline" {
        & (Join-Path $PSScriptRoot "neo4j.ps1") start
        & $py -m ml_pipeline.run_pipeline @Rest
    }
    "data" { & $py -m ml_pipeline.acquire @Rest }
    "eval" { & $py -m ml_pipeline.evaluate_all @Rest }
    "demo" { & $py scripts/demo.py @Rest }
    "test" {
        & $py -m pytest @Rest
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $py -m ruff check app ml_pipeline tests scripts
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Push-Location "app/frontend"
        npx tsc --noEmit; if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
        npm run lint; $code = $LASTEXITCODE
        Pop-Location
        exit $code
    }
    "stop" {
        Stop-Port 3000; Stop-Port 8000
        & (Join-Path $PSScriptRoot "neo4j.ps1") stop
    }
}
