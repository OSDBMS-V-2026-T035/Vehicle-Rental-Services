param(
    [string]$OutputDirectory = "$PSScriptRoot\..\database\backups"
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $envFile)) { throw "Create .env from .env.example first." }

$envValues = @{}
Get-Content -LiteralPath $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $envValues[$matches[1].Trim()] = $matches[2].Trim().Trim('"').Trim("'") }
}
$mysqlBin = Get-Command mysqldump -ErrorAction SilentlyContinue
if (-not $mysqlBin) { throw "mysqldump is not on PATH. Add the MySQL 8.4 bin directory first." }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path (Resolve-Path $OutputDirectory) "vehicle_rental-$stamp.sql"
& $mysqlBin.Source --host=$envValues.MYSQL_HOST --port=$envValues.MYSQL_PORT --user=$envValues.MYSQL_USER --password=$envValues.MYSQL_PASSWORD $envValues.MYSQL_DATABASE | Out-File -FilePath $backupPath -Encoding utf8
Write-Output "Backup created: $backupPath"
