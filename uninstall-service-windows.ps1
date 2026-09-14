$ErrorActionPreference = "Stop"

$TaskName = "Text to Voice"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Write-Host "Text to Voice autostart was removed. Local models, settings, and audio were kept."
