# Interview Coach — start both servers
# Usage: .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$python = "$root\.venv\Scripts\python.exe"
$adk    = "$root\.venv\Scripts\adk.exe"

if (-not (Test-Path $python)) {
    Write-Host "Setting up virtual environment..."
    python -m venv "$root\.venv"
    & "$root\.venv\Scripts\pip.exe" install -r "$root\requirements.txt" --quiet
}

Write-Host ""
Write-Host "Starting ADK agent server on http://127.0.0.1:8080 ..."
Start-Process -NoNewWindow powershell -ArgumentList "-Command", "cd '$root'; & '$adk' web coach --port 8080"

Start-Sleep -Seconds 3

Write-Host "Starting Voice UI on http://127.0.0.1:8081 ..."
Start-Process -NoNewWindow powershell -ArgumentList "-Command", "cd '$root'; & '$python' voice_ui.py"

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "✅ Both servers running."
Write-Host "   Open http://127.0.0.1:8081 in Chrome to start."
Write-Host ""
Write-Host "Press Ctrl+C in each terminal window to stop."
