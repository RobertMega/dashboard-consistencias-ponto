$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$required = @("PONTO_CPF", "PONTO_PASSWORD", "AUTOMATION_TOKEN", "APP_BASE_URL")
$missing = @($required | Where-Object { [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_)) })
if ($missing.Count -gt 0) {
    throw "Variáveis ausentes: $($missing -join ', ')"
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "-m automation.run_scheduled" -WorkingDirectory $projectRoot
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$defaultUser = if ([string]::IsNullOrWhiteSpace($env:USERDOMAIN)) { $env:USERNAME } else { "$env:USERDOMAIN\$env:USERNAME" }
$credential = Get-Credential -UserName $defaultUser -Message "Informe a senha do Windows para permitir execução sem sessão aberta."
$taskUser = $credential.UserName
$taskPassword = $credential.GetNetworkCredential().Password

# Remove the previous schedule names so rerunning this installer cannot leave
# stale tasks that would execute the report more than twice per day.
foreach ($legacyName in @(
    "Dashboard-Consistencias-Ponto-0600",
    "Dashboard-Consistencias-Ponto-0800",
    "Dashboard-Consistencias-Ponto-1400",
    "Dashboard-Consistencias-Ponto-1500"
)) {
    Unregister-ScheduledTask -TaskName $legacyName -Confirm:$false -ErrorAction SilentlyContinue
}

foreach ($schedule in @(
    @{ Name = "Dashboard-Consistencias-Ponto-0900"; Time = "09:00" }
)) {
    $trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($schedule.Time, "HH:mm", $null))
    Register-ScheduledTask -TaskName $schedule.Name -Action $action -Trigger $trigger -User $taskUser -Password $taskPassword -Settings $settings -Description "Atualiza o relatório D-1 do Ponto VR no dashboard." -Force | Out-Null
    Write-Output "Agendamento registrado: $($schedule.Name) às $($schedule.Time)"
}
