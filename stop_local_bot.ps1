$ErrorActionPreference = "Stop"
$projectPath = (Resolve-Path $PSScriptRoot).Path

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^python(\.exe)?$" -and
        $_.CommandLine -match "main\.py" -and
        $_.CommandLine -like "*$projectPath*"
    }

if (-not $processes) {
    Write-Host "Процесс бота не найден."
    exit 0
}

foreach ($p in $processes) {
    Stop-Process -Id $p.ProcessId -Force
    Write-Host "Остановлен PID: $($p.ProcessId)"
}
