$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-PythonCommand {
    foreach ($name in @("python", "py", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $name }
    }
    return $null
}

$py = Get-PythonCommand
if (-not $py) {
    Write-Host "Python 3.10+ is required but was not found on PATH."
    Write-Host 'Install from https://www.python.org/downloads/ and enable "Add to PATH".'
    exit 1
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    & $py -m venv venv
    $venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
}

Write-Host "Installing dependencies..."
& $venvPython -m pip install -r requirements.txt

Write-Host ""
Write-Host "Dashboard: http://127.0.0.1:8000"
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

& $venvPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
