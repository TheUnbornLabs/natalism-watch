# Registers a Windows Scheduled Task that runs the collector once a day.
# Usage:  right-click -> "Run with PowerShell"   (or run in a PowerShell window)
#         optional:  powershell -ExecutionPolicy Bypass -File setup_schedule.ps1 -Time "08:00"

param(
    [string]$Time = "08:00",
    [string]$TaskName = "NatalismDashboardDaily"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Resolve the python executable
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { Write-Error "Python not found on PATH. Install Python or add it to PATH."; exit 1 }

$script = Join-Path $here "collect.py"

$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
            -RunOnlyIfNetworkAvailable

# Remove an existing task with the same name, then register fresh
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Daily collector for the Natalism Watch dashboard" | Out-Null

Write-Host ""
Write-Host "Scheduled task '$TaskName' created." -ForegroundColor Green
Write-Host "  Runs daily at $Time"
Write-Host "  Python : $python"
Write-Host "  Script : $script"
Write-Host ""
Write-Host "If your PC is asleep/off at $Time, it runs as soon as the PC is next available."
Write-Host "To run it right now for a test:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove it later:              Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
