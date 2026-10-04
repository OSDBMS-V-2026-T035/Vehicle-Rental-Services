param(
    [switch]$CheckOnly,
    [switch]$DemoOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

function Write-Step([string]$message) {
    Write-Host "`n[RideHub] $message" -ForegroundColor Cyan
}

function Get-EnvValue([string]$key) {
    if (-not (Test-Path ".env")) {
        return ""
    }
    $escapedKey = [regex]::Escape($key)
    $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$escapedKey\s*=" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return (($line -split "=", 2)[1]).Trim().Trim('"').Trim("'")
}

function Set-EnvValue([string]$key, [string]$value) {
    $lines = @()
    if (Test-Path ".env") {
        $lines = @(Get-Content ".env")
    }
    $escapedKey = [regex]::Escape($key)
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^\s*$escapedKey\s*=") {
            $found = $true
            "$key=$value"
        } else {
            $line
        }
    }
    if (-not $found) {
        $updated += "$key=$value"
    }
    Set-Content -Path ".env" -Value $updated -Encoding utf8
}

function Get-RootPasswordPopup {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "RideHub - MySQL Setup"
    $form.Size = New-Object System.Drawing.Size(430, 185)
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true

    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Enter your local MySQL root password:`nIt is used only to prepare RideHub's database."
    $label.AutoSize = $true
    $label.Location = New-Object System.Drawing.Point(18, 16)

    $passwordBox = New-Object System.Windows.Forms.TextBox
    $passwordBox.Location = New-Object System.Drawing.Point(18, 68)
    $passwordBox.Size = New-Object System.Drawing.Size(375, 24)
    $passwordBox.UseSystemPasswordChar = $true

    $okButton = New-Object System.Windows.Forms.Button
    $okButton.Text = "Verify & Continue"
    $okButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $okButton.Location = New-Object System.Drawing.Point(205, 105)
    $okButton.Size = New-Object System.Drawing.Size(135, 28)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = "Cancel"
    $cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $cancelButton.Location = New-Object System.Drawing.Point(348, 105)
    $cancelButton.Size = New-Object System.Drawing.Size(68, 28)

    $form.Controls.AddRange(@($label, $passwordBox, $okButton, $cancelButton))
    $form.AcceptButton = $okButton
    $form.CancelButton = $cancelButton
    $form.Add_Shown({ $passwordBox.Focus() })

    if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        throw "MySQL setup was cancelled."
    }

    $securePassword = New-Object System.Security.SecureString
    foreach ($character in $passwordBox.Text.ToCharArray()) {
        $securePassword.AppendChar($character)
    }
    $securePassword.MakeReadOnly()
    return $securePassword
}

Write-Step "Checking Python environment"
$pythonCommand = Get-Command python -ErrorAction Stop
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Step "Creating the project virtual environment"
    & $pythonCommand.Source -m venv .venv
}

Write-Step "Checking project dependencies"
& $venvPython -c "import django, MySQLdb" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Installing project dependencies"
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. Check your internet connection and run the launcher again."
    }
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

$appPassword = Get-EnvValue "MYSQL_PASSWORD"
if ([string]::IsNullOrWhiteSpace($appPassword) -or $appPassword -eq "change-me") {
    $appPassword = "RideHubDemo@2026"
}
Set-EnvValue "MYSQL_DATABASE" "vehicle_rental"
Set-EnvValue "MYSQL_USER" "vehicle_rental_user"
Set-EnvValue "MYSQL_PASSWORD" $appPassword
Set-EnvValue "MYSQL_HOST" "127.0.0.1"
Set-EnvValue "MYSQL_PORT" "3306"

$mysqlExe = ""
if (-not $DemoOnly) {
    $mysqlExe = "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"
    if (-not (Test-Path $mysqlExe)) {
        $mysqlCommand = Get-Command mysql -ErrorAction SilentlyContinue
        if ($mysqlCommand) {
            $mysqlExe = $mysqlCommand.Source
        } else {
            throw "MySQL 8.4 was not found. Install/start MySQL 8.4, then run this file again."
        }
    }

    $mysqlService = Get-Service -Name "MySQL84" -ErrorAction SilentlyContinue
    if ($mysqlService -and $mysqlService.Status -ne "Running") {
        Write-Step "Starting MySQL 8.4 service"
        Start-Service -Name "MySQL84"
        Start-Sleep -Seconds 2
    }
}

if ($CheckOnly) {
    $message = if ($DemoOnly) { "Demo launcher checks passed. .env is ready." } else { "Launcher checks passed. .env is ready and MySQL client was found." }
    Write-Host "`n[RideHub] $message" -ForegroundColor Green
    exit 0
}

if (-not $DemoOnly) {
    Write-Step "Checking the Vehicle Rental database"
    $databaseReady = $false
    $appDefaults = [IO.Path]::GetTempFileName()
    try {
        @(
            "[client]",
            "host=127.0.0.1",
            "user=vehicle_rental_user",
            "password=$appPassword"
        ) | Set-Content -Path $appDefaults -Encoding ascii
        & $mysqlExe "--defaults-extra-file=$appDefaults" --batch --skip-column-names -e "USE vehicle_rental; SELECT 1;" 2>$null
        $databaseReady = $LASTEXITCODE -eq 0
    } finally {
        if (Test-Path $appDefaults) {
            Remove-Item -LiteralPath $appDefaults -Force
        }
    }

    if (-not $databaseReady) {
        Write-Step "Preparing the Vehicle Rental database"
        $secureRootPassword = Get-RootPasswordPopup
        $rootPasswordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureRootPassword)
        $rootPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($rootPasswordPointer)
        $tempDefaults = [IO.Path]::GetTempFileName()
        $sqlPassword = $appPassword.Replace("'", "''")
        $sql = @"
CREATE DATABASE IF NOT EXISTS vehicle_rental CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'vehicle_rental_user'@'localhost' IDENTIFIED BY '$sqlPassword';
CREATE USER IF NOT EXISTS 'vehicle_rental_user'@'127.0.0.1' IDENTIFIED BY '$sqlPassword';
ALTER USER 'vehicle_rental_user'@'localhost' IDENTIFIED BY '$sqlPassword';
ALTER USER 'vehicle_rental_user'@'127.0.0.1' IDENTIFIED BY '$sqlPassword';
GRANT ALL PRIVILEGES ON vehicle_rental.* TO 'vehicle_rental_user'@'localhost';
GRANT ALL PRIVILEGES ON vehicle_rental.* TO 'vehicle_rental_user'@'127.0.0.1';
FLUSH PRIVILEGES;
"@

        try {
            @(
                "[client]",
                "host=127.0.0.1",
                "user=root",
                "password=$rootPassword"
            ) | Set-Content -Path $tempDefaults -Encoding ascii
            & $mysqlExe "--defaults-extra-file=$tempDefaults" --batch --skip-column-names -e $sql
            if ($LASTEXITCODE -ne 0) {
                throw "MySQL setup failed. Check the root password and try again."
            }
        } finally {
            if (Test-Path $tempDefaults) {
                Remove-Item -LiteralPath $tempDefaults -Force
            }
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($rootPasswordPointer)
        }
    }

    Write-Step "Applying Django database migrations"
    & $venvPython backend/manage.py check
    & $venvPython backend/manage.py migrate --noinput
    & $venvPython backend/manage.py collectstatic --noinput

    Write-Step "Installing MySQL reporting view and maintenance procedure"
    $schemaDefaults = [IO.Path]::GetTempFileName()
    try {
        @(
            "[client]",
            "host=127.0.0.1",
            "user=vehicle_rental_user",
            "password=$appPassword"
        ) | Set-Content -Path $schemaDefaults -Encoding ascii
        Get-Content -Raw "database/schema/reporting_views.sql" | & $mysqlExe "--defaults-extra-file=$schemaDefaults" --database=vehicle_rental
        if ($LASTEXITCODE -ne 0) { throw "Reporting view installation failed." }
        Get-Content -Raw "database/schema/stored_procedures.sql" | & $mysqlExe "--defaults-extra-file=$schemaDefaults" --database=vehicle_rental
        if ($LASTEXITCODE -ne 0) { throw "Stored procedure installation failed." }
    } finally {
        if (Test-Path $schemaDefaults) { Remove-Item -LiteralPath $schemaDefaults -Force }
    }
} else {
    Write-Step "Starting mentor demo without requiring database login"
    & $venvPython backend/manage.py check
}

$serverUrl = "http://127.0.0.1:8000/"
$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $portInUse) {
    Write-Step "Starting Django on $serverUrl"
    if ($DemoOnly) {
        $serverArguments = @("scripts/preview_server.py")
    } else {
        $serverArguments = @("backend/manage.py", "runserver", "127.0.0.1:8000", "--noreload")
    }
    Start-Process -FilePath $venvPython -ArgumentList $serverArguments -WorkingDirectory $projectRoot -WindowStyle Normal
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $serverUrl -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
        }
    }
    if (-not $ready) {
        throw "Django did not become ready on port 8000. Check the server window."
    }
} else {
    Write-Host "`n[RideHub] Port 8000 is already in use; opening the existing server." -ForegroundColor Yellow
}

$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
$chrome = $chromePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($chrome) {
    Start-Process -FilePath $chrome -ArgumentList @("--new-tab", $serverUrl)
} else {
    Start-Process $serverUrl
}

Write-Host "`n[RideHub] Done. Website opened at $serverUrl" -ForegroundColor Green
