$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $projectRoot
try {
    & ".\.venv\Scripts\python.exe" "backend\manage.py" expire_bookings --older-than-hours 24
    & ".\.venv\Scripts\python.exe" "backend\manage.py" detect_deadlocks
} finally {
    Pop-Location
}
