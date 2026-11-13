$ErrorActionPreference = 'Stop'
$partyRoot = Split-Path -Parent $PSScriptRoot
$partyPython = Join-Path $partyRoot '.venv-party\Scripts\python.exe'
$partyStatusPath = Join-Path $PSScriptRoot 'status.json'
if (Test-Path -LiteralPath $partyStatusPath) {
    $partyStatus = Get-Content -LiteralPath $partyStatusPath -Raw | ConvertFrom-Json
    if ($partyStatus.pid) {
        $partyExisting = Get-CimInstance Win32_Process -Filter "ProcessId = $($partyStatus.pid)"
        if ($partyExisting -and $partyExisting.CommandLine -match 'processing.party_sentiment') {
            Write-Output "Analysis already running, PID $($partyStatus.pid)."
            exit 0
        }
    }
}
$partyJob = Start-Process -FilePath $partyPython -ArgumentList '-u','-m','processing.party_sentiment' -WorkingDirectory $partyRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'run.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'run.stderr.log') -PassThru
$partyJob.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'launched_pid.txt')
Write-Output "Started resumable local analysis, launcher PID $($partyJob.Id). See status.json for worker PID and progress."
