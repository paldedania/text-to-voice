$ErrorActionPreference = "Stop"

$TaskName = "Text to Voice"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectDir ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $Python)) {
    throw "The project environment is missing. Follow the setup command in README.md."
}

$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Arguments = '-m uvicorn app.main:app --host 127.0.0.1 --port 8765'
$Action = New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
$Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Principal $Principal -Settings $Settings `
    -Description "Local Text to Voice server" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Text to Voice is installed and will start when you sign in."
Write-Host "Open http://127.0.0.1:8765/ after the server starts."
