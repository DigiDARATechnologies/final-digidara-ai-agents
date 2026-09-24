<#!
.SYNOPSIS
Starts the local orchestrator and Resume Builder agent, then confirms that the
agent registered successfully.
#>

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$orchestratorDir = Join-Path $projectRoot 'agents\orchestrator'
$resumeBuilderDir = Join-Path $projectRoot 'agents\resume_builder_agent\backend'
$orchestratorPython = Join-Path $orchestratorDir '.venv\Scripts\python.exe'
$resumeBuilderPython = Join-Path $resumeBuilderDir '.venv\Scripts\python.exe'

foreach ($python in @($orchestratorPython, $resumeBuilderPython)) {
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Python virtual environment is missing: $python"
    }
}

function Start-LocalService {
    param(
        [int]$Port,
        [string]$Python,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [string]$Name
    )

    $existing = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($existing) {
        Write-Host "$Name is already listening on port $Port."
        return
    }

    $stdout = Join-Path $WorkingDirectory "$Name.stdout.log"
    $stderr = Join-Path $WorkingDirectory "$Name.stderr.log"
    Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-Host "Started $Name on port $Port."
}

Start-LocalService -Port 8100 -Python $orchestratorPython `
    -Arguments @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8100') `
    -WorkingDirectory $orchestratorDir -Name 'orchestrator'

Start-Sleep -Seconds 2

Start-LocalService -Port 5010 -Python $resumeBuilderPython -Arguments @('run.py') `
    -WorkingDirectory $resumeBuilderDir -Name 'resume_builder'

Start-Sleep -Seconds 3

try {
    $agent = Invoke-RestMethod -Uri 'http://127.0.0.1:8100/registry/agents' -TimeoutSec 5 |
        Where-Object { $_.agent_name -eq 'resume_builder_agent' } |
        Select-Object -First 1

    if ($agent) {
        Write-Host 'Resume Builder registered successfully.' -ForegroundColor Green
    } else {
        Write-Warning 'Resume Builder is still not registered. Review agents\resume_builder_agent\backend\resume_builder.stderr.log.'
    }
} catch {
    Write-Warning "Could not verify registration: $($_.Exception.Message)"
}
