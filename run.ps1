$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Uvicorn = Join-Path $ProjectDir ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $Uvicorn)) {
    throw "The project environment is missing. Follow the setup command in README.md."
}

Set-Location $ProjectDir
& $Uvicorn "app.main:app" --host "127.0.0.1" --port "8765"
exit $LASTEXITCODE
