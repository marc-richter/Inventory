# ============================================================
# Inventarprogramm - Verwaltung (Windows)
# Grafische App (WinForms) fuer: Uebersicht, Starten/Stoppen,
# Erstinstallation/Update und Deinstallation.
# ============================================================

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$BackupsDir = Join-Path $ProjectDir "backups"
$CertsDir   = Join-Path $ProjectDir "certs"
$EnvPath    = Join-Path $ProjectDir ".env"
$VersionFile = Join-Path $ProjectDir "VERSION"
$MarkerFile  = Join-Path $BackupsDir ".installed_version"

# ------------------------------------------------------------------
# Hilfsfunktionen (laufen im UI-Prozess, nur fuer Anzeige/Lesevorgaenge)
# ------------------------------------------------------------------
function Test-DockerReady {
    try {
        docker info *>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-Installed {
    return (Test-Path $EnvPath)
}

function Get-EnvValues {
    $result = @{ WEB_PORT = "8080"; WEB_TLS_PORT = "8443" }
    if (Test-Path $EnvPath) {
        Get-Content $EnvPath | ForEach-Object {
            if ($_ -match "^([A-Z_]+)=(.*)$") { $result[$Matches[1]] = $Matches[2] }
        }
    }
    return $result
}

function Get-AvailableVersion {
    if (Test-Path $VersionFile) {
        return (Get-Content $VersionFile -Raw).Trim()
    }
    return "unbekannt"
}

function Get-InstalledVersion {
    if (Test-Path $MarkerFile) {
        return (Get-Content $MarkerFile -Raw).Trim()
    }
    return "nicht installiert"
}

function Get-LocalIp {
    try {
        $ip = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet|Virtual" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1 -ExpandProperty IPAddress
        return $ip
    } catch {
        return $null
    }
}

function Test-AppRunning {
    if (-not (Test-DockerReady)) { return $false }
    Push-Location $ProjectDir
    try {
        $running = (& docker compose ps --status running -q 2>$null)
        return [bool]$running
    } finally {
        Pop-Location
    }
}

function Get-DirSize($path) {
    if (-not (Test-Path $path)) { return "-" }
    try {
        $bytes = (Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        if (-not $bytes) { $bytes = 0 }
        return Format-Bytes $bytes
    } catch {
        return "-"
    }
}

function Format-Bytes($bytes) {
    if ($bytes -ge 1GB) { return "{0:N1} GB" -f ($bytes / 1GB) }
    if ($bytes -ge 1MB) { return "{0:N1} MB" -f ($bytes / 1MB) }
    if ($bytes -ge 1KB) { return "{0:N1} KB" -f ($bytes / 1KB) }
    return "$bytes B"
}

function Get-DataVolumeSizeText {
    if (-not (Test-DockerReady)) { return "-" }
    Push-Location $ProjectDir
    try {
        $cid = (& docker compose ps -a -q backend 2>$null)
        if (-not $cid) { return "-" }
        $vol = (& docker inspect $cid --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' 2>$null)
        if (-not $vol) { return "-" }
        $out = (& docker run --rm -v "${vol}:/data" alpine:3.19 du -sh /data 2>$null)
        if ($out) { return ($out -split "\s+")[0] }
        return "-"
    } catch {
        return "-"
    } finally {
        Pop-Location
    }
}

function Get-ImagesSizeLines {
    if (-not (Test-DockerReady)) { return @("-") }
    Push-Location $ProjectDir
    try {
        $images = (& docker compose config --images 2>$null)
        $lines = @()
        foreach ($img in $images) {
            if (-not $img) { continue }
            $size = (& docker images $img --format "{{.Size}}" 2>$null | Select-Object -First 1)
            if ($size) { $lines += "$img : $size" }
        }
        if ($lines.Count -eq 0) { $lines = @("(noch keine Images gebaut)") }
        return $lines
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------
# Hauptfenster
# ------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "Inventarprogramm - Verwaltung"
$form.Size = New-Object System.Drawing.Size(660, 720)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$y = 15

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "Inventarprogramm - Verwaltung"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$lblTitle.Location = New-Object System.Drawing.Point(15, $y)
$lblTitle.Size = New-Object System.Drawing.Size(500, 30)
$form.Controls.Add($lblTitle)
$y += 40

$lblProjectDir = New-Object System.Windows.Forms.Label
$lblProjectDir.Text = "Projektverzeichnis: $ProjectDir"
$lblProjectDir.Location = New-Object System.Drawing.Point(15, $y)
$lblProjectDir.Size = New-Object System.Drawing.Size(620, 20)
$lblProjectDir.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$form.Controls.Add($lblProjectDir)
$y += 30

$grpStatus = New-Object System.Windows.Forms.GroupBox
$grpStatus.Text = "Uebersicht"
$grpStatus.Location = New-Object System.Drawing.Point(15, $y)
$grpStatus.Size = New-Object System.Drawing.Size(615, 190)
$form.Controls.Add($grpStatus)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Location = New-Object System.Drawing.Point(15, 25)
$lblStatus.Size = New-Object System.Drawing.Size(580, 20)
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$grpStatus.Controls.Add($lblStatus)

$lblVersions = New-Object System.Windows.Forms.Label
$lblVersions.Location = New-Object System.Drawing.Point(15, 50)
$lblVersions.Size = New-Object System.Drawing.Size(580, 40)
$grpStatus.Controls.Add($lblVersions)

$lblUrls = New-Object System.Windows.Forms.Label
$lblUrls.Location = New-Object System.Drawing.Point(15, 95)
$lblUrls.Size = New-Object System.Drawing.Size(580, 80)
$grpStatus.Controls.Add($lblUrls)

$y += 200

$grpSize = New-Object System.Windows.Forms.GroupBox
$grpSize.Text = "Speicherbelegung"
$grpSize.Location = New-Object System.Drawing.Point(15, $y)
$grpSize.Size = New-Object System.Drawing.Size(615, 130)
$form.Controls.Add($grpSize)

$lstSize = New-Object System.Windows.Forms.ListBox
$lstSize.Location = New-Object System.Drawing.Point(15, 20)
$lstSize.Size = New-Object System.Drawing.Size(580, 95)
$grpSize.Controls.Add($lstSize)

$y += 140

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = "Aktualisieren"
$btnRefresh.Location = New-Object System.Drawing.Point(15, $y)
$btnRefresh.Size = New-Object System.Drawing.Size(120, 32)
$form.Controls.Add($btnRefresh)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "Starten"
$btnStart.Location = New-Object System.Drawing.Point(145, $y)
$btnStart.Size = New-Object System.Drawing.Size(120, 32)
$btnStart.BackColor = [System.Drawing.Color]::FromArgb(210, 245, 210)
$form.Controls.Add($btnStart)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = "Stoppen"
$btnStop.Location = New-Object System.Drawing.Point(275, $y)
$btnStop.Size = New-Object System.Drawing.Size(120, 32)
$btnStop.BackColor = [System.Drawing.Color]::FromArgb(255, 235, 200)
$form.Controls.Add($btnStop)

$btnAdvancedToggle = New-Object System.Windows.Forms.Button
$btnAdvancedToggle.Text = "Erweitert  >>"
$btnAdvancedToggle.Location = New-Object System.Drawing.Point(495, $y)
$btnAdvancedToggle.Size = New-Object System.Drawing.Size(135, 32)
$form.Controls.Add($btnAdvancedToggle)

$y += 42

$pnlAdvanced = New-Object System.Windows.Forms.Panel
$pnlAdvanced.Location = New-Object System.Drawing.Point(15, $y)
$pnlAdvanced.Size = New-Object System.Drawing.Size(615, 55)
$pnlAdvanced.Visible = $false
$pnlAdvanced.BorderStyle = "FixedSingle"
$form.Controls.Add($pnlAdvanced)

$btnInstallUpdate = New-Object System.Windows.Forms.Button
$btnInstallUpdate.Text = "Erstinstallation / Update..."
$btnInstallUpdate.Location = New-Object System.Drawing.Point(10, 12)
$btnInstallUpdate.Size = New-Object System.Drawing.Size(220, 30)
$pnlAdvanced.Controls.Add($btnInstallUpdate)

$btnRestore = New-Object System.Windows.Forms.Button
$btnRestore.Text = "Komplett-Backup einspielen..."
$btnRestore.Location = New-Object System.Drawing.Point(240, 12)
$btnRestore.Size = New-Object System.Drawing.Size(190, 30)
$pnlAdvanced.Controls.Add($btnRestore)

$btnUninstall = New-Object System.Windows.Forms.Button
$btnUninstall.Text = "Deinstallation..."
$btnUninstall.Location = New-Object System.Drawing.Point(440, 12)
$btnUninstall.Size = New-Object System.Drawing.Size(160, 30)
$btnUninstall.ForeColor = [System.Drawing.Color]::DarkRed
$pnlAdvanced.Controls.Add($btnUninstall)

$y += 65

$lblLog = New-Object System.Windows.Forms.Label
$lblLog.Text = "Protokoll:"
$lblLog.Location = New-Object System.Drawing.Point(15, $y)
$lblLog.Size = New-Object System.Drawing.Size(200, 20)
$form.Controls.Add($lblLog)
$y += 22

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Vertical"
$txtLog.ReadOnly = $true
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 9)
$txtLog.Location = New-Object System.Drawing.Point(15, $y)
$txtLog.Size = New-Object System.Drawing.Size(615, 150)
$form.Controls.Add($txtLog)

function Add-Log([string]$text) {
    $txtLog.AppendText("$text`r`n")
}

# ------------------------------------------------------------------
# Status aktualisieren
# ------------------------------------------------------------------
function Update-StatusView {
    $lstSize.Items.Clear()
    if (-not (Test-Installed)) {
        $lblStatus.Text = "Status: keine Installation vorhanden"
        $lblStatus.ForeColor = [System.Drawing.Color]::DarkOrange
        $lblVersions.Text = "Verfuegbare Version: $(Get-AvailableVersion)`r`nBitte 'Erweitert' -> 'Erstinstallation / Update' ausfuehren."
        $lblUrls.Text = ""
        $lstSize.Items.Add("(noch keine Installation)")
        return
    }

    $running = Test-AppRunning
    if ($running) {
        $lblStatus.Text = "Status: laeuft"
        $lblStatus.ForeColor = [System.Drawing.Color]::ForestGreen
    } else {
        $lblStatus.Text = "Status: gestoppt"
        $lblStatus.ForeColor = [System.Drawing.Color]::DarkOrange
    }

    $instVer = Get-InstalledVersion
    $availVer = Get-AvailableVersion
    $verText = "Installierte Version: $instVer`r`nVerfuegbare Version:  $availVer"
    if ($instVer -ne $availVer -and $instVer -ne "nicht installiert") {
        $verText += "  -> Update verfuegbar (siehe 'Erweitert')"
    }
    $lblVersions.Text = $verText

    $envVals = Get-EnvValues
    $webPort = $envVals["WEB_PORT"]
    $tlsPort = $envVals["WEB_TLS_PORT"]
    $ip = Get-LocalIp
    $urlText = "Adresse (lokal):        http://localhost:$webPort`r`n"
    if ($ip) {
        $urlText += "Adresse (Netzwerk):     http://${ip}:$webPort`r`n"
        $urlText += "Adresse (HTTPS/Kamera): https://${ip}:$tlsPort"
    }
    $lblUrls.Text = $urlText

    $lstSize.Items.Add("Datenbank/Bilder (Docker-Volume): $(Get-DataVolumeSizeText)")
    $lstSize.Items.Add("Backup-Ordner (.\backups):        $(Get-DirSize $BackupsDir)")
    $lstSize.Items.Add("HTTPS-Zertifikate (.\certs):       $(Get-DirSize $CertsDir)")
    foreach ($line in (Get-ImagesSizeLines)) { $lstSize.Items.Add("Image: $line") }
}

# ------------------------------------------------------------------
# Hintergrund-Jobs (damit die Oberflaeche nicht einfriert)
# ------------------------------------------------------------------
$global:CurrentJob = $null
$global:OnJobDone = $null

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 800

function Set-BusyState([bool]$busy) {
    $btnStart.Enabled = -not $busy
    $btnStop.Enabled = -not $busy
    $btnRefresh.Enabled = -not $busy
    $btnInstallUpdate.Enabled = -not $busy
    $btnRestore.Enabled = -not $busy
    $btnUninstall.Enabled = -not $busy
    $btnAdvancedToggle.Enabled = -not $busy
}

function Start-BackgroundAction([scriptblock]$scriptBlock, [object[]]$argList, [scriptblock]$onDone) {
    if ($global:CurrentJob) {
        Add-Log "Es laeuft bereits eine Aktion - bitte warten."
        return
    }
    Set-BusyState $true
    Add-Log "--- Aktion gestartet ---"
    $global:CurrentJob = Start-Job -ScriptBlock $scriptBlock -ArgumentList $argList
    $global:OnJobDone = $onDone
    $timer.Start()
}

$timer.Add_Tick({
    if (-not $global:CurrentJob) { $timer.Stop(); return }

    $newOutput = Receive-Job -Job $global:CurrentJob
    foreach ($line in $newOutput) { Add-Log "$line" }

    if ($global:CurrentJob.State -in @("Completed", "Failed", "Stopped")) {
        $timer.Stop()
        $finalOutput = Receive-Job -Job $global:CurrentJob
        foreach ($line in $finalOutput) { Add-Log "$line" }
        Remove-Job -Job $global:CurrentJob -Force
        Add-Log "--- Aktion beendet ($($global:CurrentJob.State)) ---"
        $global:CurrentJob = $null
        Set-BusyState $false
        Update-StatusView
        if ($global:OnJobDone) {
            & $global:OnJobDone
        }
        $global:OnJobDone = $null
    }
})

# ------------------------------------------------------------------
# Wiederverwendbare Job-Skriptbloecke
# ------------------------------------------------------------------

$sbEnsureCert = {
    param($ProjectDir)
    $CertsDir = Join-Path $ProjectDir "certs"
    New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null
    $certPath = Join-Path $CertsDir "cert.pem"
    $keyPath = Join-Path $CertsDir "key.pem"
    if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
        Write-Output "Erzeuge selbstsigniertes HTTPS-Zertifikat (einmalig)..."
        $CertIp = $null
        try {
            $CertIp = (Get-NetIPAddress -AddressFamily IPv4 |
                Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet|Virtual" -and $_.IPAddress -notlike "169.254.*" } |
                Select-Object -First 1 -ExpandProperty IPAddress)
        } catch { $CertIp = $null }
        if (-not $CertIp) { $CertIp = "127.0.0.1" }
        $certsDirDocker = $CertsDir -replace "\\", "/"
        docker run --rm -v "${certsDirDocker}:/certs" alpine:3.19 sh -c "apk add --no-cache openssl >/dev/null 2>&1; openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -keyout /certs/key.pem -out /certs/cert.pem -subj '/CN=inventarprogramm' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$CertIp'" 2>&1 | Out-Null
        if ((Test-Path $certPath) -and (Test-Path $keyPath)) {
            Write-Output "HTTPS-Zertifikat wurde erstellt."
        } else {
            Write-Output "Zertifikat konnte nicht automatisch erstellt werden."
        }
    }
}

function Wait-ForHealthText($ProjectDir) {
    $envPath = Join-Path $ProjectDir ".env"
    $webPort = "8080"
    if (Test-Path $envPath) {
        Get-Content $envPath | ForEach-Object {
            if ($_ -match "^WEB_PORT=(.*)$") { $script:webPort = $Matches[1] }
        }
    }
    return $webPort
}

$sbStart = {
    param($ProjectDir)
    Set-Location $ProjectDir
    Write-Output "Starte die Anwendung..."
    docker compose up -d 2>&1
    Write-Output "Warte, bis die Anwendung erreichbar ist..."
    $webPort = "8080"
    if (Test-Path ".env") {
        Get-Content ".env" | ForEach-Object { if ($_ -match "^WEB_PORT=(.*)$") { $webPort = $Matches[1] } }
    }
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($ready) { Write-Output "Die Anwendung laeuft." } else { Write-Output "Die Anwendung antwortet noch nicht ganz - kurz warten und Seite neu laden." }
    Start-Process "http://localhost:$webPort"
}

$sbStop = {
    param($ProjectDir)
    Set-Location $ProjectDir
    Write-Output "Stoppe die Anwendung (Daten und Einstellungen bleiben erhalten)..."
    docker compose stop 2>&1
    Write-Output "Die Anwendung wurde gestoppt."
}

$sbWriteMarker = {
    param($ProjectDir)
    $versionFile = Join-Path $ProjectDir "VERSION"
    $backupsDir = Join-Path $ProjectDir "backups"
    New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null
    $version = "unbekannt"
    if (Test-Path $versionFile) { $version = (Get-Content $versionFile -Raw).Trim() }
    Set-Content -Path (Join-Path $backupsDir ".installed_version") -Value $version -NoNewline
}

$sbUpdateExisting = {
    param($ProjectDir)
    Set-Location $ProjectDir
    Write-Output "Update wird durchgefuehrt - alle Daten bleiben vollstaendig erhalten."
    docker compose up -d --build 2>&1
    Write-Output "Warte, bis die Anwendung erreichbar ist..."
    $webPort = "8080"
    if (Test-Path ".env") { Get-Content ".env" | ForEach-Object { if ($_ -match "^WEB_PORT=(.*)$") { $webPort = $Matches[1] } } }
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($ready) { Write-Output "Update abgeschlossen. Die Anwendung laeuft." } else { Write-Output "Update abgeschlossen, Anwendung antwortet aber noch nicht ganz." }
    $versionFile = Join-Path $ProjectDir "VERSION"
    $backupsDir = Join-Path $ProjectDir "backups"
    New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null
    $version = "unbekannt"
    if (Test-Path $versionFile) { $version = (Get-Content $versionFile -Raw).Trim() }
    Set-Content -Path (Join-Path $backupsDir ".installed_version") -Value $version -NoNewline
}

$sbReinstallKeepData = {
    param($ProjectDir)
    Set-Location $ProjectDir
    Write-Output "Neuinstallation (Daten bleiben erhalten): Container/Images werden neu gebaut..."
    docker compose down --rmi all 2>&1

    $CertsDir = Join-Path $ProjectDir "certs"
    New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null
    $certPath = Join-Path $CertsDir "cert.pem"
    $keyPath = Join-Path $CertsDir "key.pem"
    if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
        $CertIp = $null
        try {
            $CertIp = (Get-NetIPAddress -AddressFamily IPv4 |
                Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet|Virtual" -and $_.IPAddress -notlike "169.254.*" } |
                Select-Object -First 1 -ExpandProperty IPAddress)
        } catch { $CertIp = $null }
        if (-not $CertIp) { $CertIp = "127.0.0.1" }
        $certsDirDocker = $CertsDir -replace "\\", "/"
        docker run --rm -v "${certsDirDocker}:/certs" alpine:3.19 sh -c "apk add --no-cache openssl >/dev/null 2>&1; openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -keyout /certs/key.pem -out /certs/cert.pem -subj '/CN=inventarprogramm' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$CertIp'" 2>&1 | Out-Null
    }

    docker compose up -d --build 2>&1
    Write-Output "Warte, bis die Anwendung erreichbar ist..."
    $webPort = "8080"
    if (Test-Path ".env") { Get-Content ".env" | ForEach-Object { if ($_ -match "^WEB_PORT=(.*)$") { $webPort = $Matches[1] } } }
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($ready) { Write-Output "Neuinstallation abgeschlossen. Die Anwendung laeuft." } else { Write-Output "Neuinstallation abgeschlossen, Anwendung antwortet aber noch nicht ganz." }
    $versionFile = Join-Path $ProjectDir "VERSION"
    $backupsDir = Join-Path $ProjectDir "backups"
    New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null
    $version = "unbekannt"
    if (Test-Path $versionFile) { $version = (Get-Content $versionFile -Raw).Trim() }
    Set-Content -Path (Join-Path $backupsDir ".installed_version") -Value $version -NoNewline
}

$sbReinstallDeleteData = {
    param($ProjectDir, $DeleteBackups)
    Set-Location $ProjectDir
    Write-Output "Loesche alle Daten und entferne Container/Images/Volumes..."
    docker compose down -v --rmi all 2>&1
    if ($DeleteBackups) {
        $backupsDir = Join-Path $ProjectDir "backups"
        if (Test-Path $backupsDir) { Remove-Item -Recurse -Force $backupsDir; Write-Output "Backup-Ordner geloescht." }
    }
    $envPath = Join-Path $ProjectDir ".env"
    if (Test-Path $envPath) { Remove-Item -Force $envPath }
    Write-Output "Alte Daten wurden entfernt."
}

$sbFreshInstall = {
    param($ProjectDir, $AdminUser, $AdminPassword, $WebPort, $BackupHostPath, $WebTlsPort, $OrgName, $LogoPath)
    Set-Location $ProjectDir

    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $SecretKey = [System.BitConverter]::ToString($bytes) -replace "-", ""

    # Optionales Logo aus der Erstinstallation uebernehmen: in ./config kopieren,
    # das per docker-compose schreibgeschuetzt nach /app/initial gemountet wird.
    $LogoEnv = ""
    if ($LogoPath -and (Test-Path $LogoPath)) {
        $destExt = ""
        switch ([System.IO.Path]::GetExtension($LogoPath).ToLower()) {
            ".png"  { $destExt = ".png" }
            ".jpg"  { $destExt = ".jpg" }
            ".jpeg" { $destExt = ".jpg" }
            ".svg"  { $destExt = ".svg" }
            ".webp" { $destExt = ".webp" }
        }
        if ($destExt) {
            $configDir = Join-Path $ProjectDir "config"
            New-Item -ItemType Directory -Force -Path $configDir | Out-Null
            try {
                Copy-Item -LiteralPath $LogoPath -Destination (Join-Path $configDir "logo$destExt") -Force
                $LogoEnv = "/app/initial/logo$destExt"
                Write-Output "Logo uebernommen."
            } catch {
                Write-Output "Logo konnte nicht kopiert werden - wird uebersprungen."
            }
        } else {
            Write-Output "Nicht unterstuetztes Logo-Format - wird uebersprungen (nur PNG/JPG/SVG/WEBP)."
        }
    }

    @"
SECRET_KEY=$SecretKey
DEFAULT_ADMIN_USERNAME=$AdminUser
DEFAULT_ADMIN_PASSWORD=$AdminPassword
ACCESS_TOKEN_EXPIRE_MINUTES=720
WEB_PORT=$WebPort
WEB_TLS_PORT=$WebTlsPort
BACKUP_HOST_PATH=$BackupHostPath
DEFAULT_ORG_NAME=$OrgName
DEFAULT_LOGO_FILE=$LogoEnv
"@ | Out-File -FilePath (Join-Path $ProjectDir ".env") -Encoding utf8

    Write-Output "Konfigurationsdatei .env wurde erstellt."

    $CertsDir = Join-Path $ProjectDir "certs"
    New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null
    $certPath = Join-Path $CertsDir "cert.pem"
    $keyPath = Join-Path $CertsDir "key.pem"
    if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
        Write-Output "Erzeuge selbstsigniertes HTTPS-Zertifikat (einmalig)..."
        $CertIp = $null
        try {
            $CertIp = (Get-NetIPAddress -AddressFamily IPv4 |
                Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet|Virtual" -and $_.IPAddress -notlike "169.254.*" } |
                Select-Object -First 1 -ExpandProperty IPAddress)
        } catch { $CertIp = $null }
        if (-not $CertIp) { $CertIp = "127.0.0.1" }
        $certsDirDocker = $CertsDir -replace "\\", "/"
        docker run --rm -v "${certsDirDocker}:/certs" alpine:3.19 sh -c "apk add --no-cache openssl >/dev/null 2>&1; openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -keyout /certs/key.pem -out /certs/cert.pem -subj '/CN=inventarprogramm' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$CertIp'" 2>&1 | Out-Null
    }

    Write-Output "Container werden gebaut und gestartet - das kann beim ersten Mal einige Minuten dauern..."
    docker compose up -d --build 2>&1
    Write-Output "Warte, bis die Anwendung erreichbar ist..."
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:$WebPort/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 2 }
    }
    if ($ready) { Write-Output "Fertig! Die Anwendung laeuft." } else { Write-Output "Die Anwendung antwortet noch nicht ganz - kurz warten und Seite neu laden." }

    $versionFile = Join-Path $ProjectDir "VERSION"
    $backupsDir = Join-Path $ProjectDir "backups"
    New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null
    $version = "unbekannt"
    if (Test-Path $versionFile) { $version = (Get-Content $versionFile -Raw).Trim() }
    Set-Content -Path (Join-Path $backupsDir ".installed_version") -Value $version -NoNewline

    if ($AdminPassword) {
        Write-Output ""
        Write-Output "Erster Login:"
        Write-Output "   Benutzername: $AdminUser"
        Write-Output "   Passwort:     $AdminPassword"
        Write-Output "Bitte nach dem ersten Login unter 'Mein Konto' Passwort/PIN aendern!"
    }
    Start-Process "http://localhost:$WebPort"
}

$sbUninstall = {
    param($ProjectDir, $RemoveVolumes, $RemoveImages, $DeleteBackups, $DeleteCerts)
    Set-Location $ProjectDir
    Write-Output "Container werden gestoppt und entfernt..."
    docker compose down 2>&1

    if ($RemoveVolumes -or $RemoveImages) {
        $downArgs = @("compose", "down")
        if ($RemoveVolumes) { $downArgs += "-v" }
        if ($RemoveImages)  { $downArgs += "--rmi"; $downArgs += "all" }
        Write-Output "Fuehre aus: docker $($downArgs -join ' ')"
        & docker @downArgs 2>&1
    }

    if ($RemoveVolumes) {
        if ($DeleteBackups) {
            $backupsDir = Join-Path $ProjectDir "backups"
            if (Test-Path $backupsDir) { Remove-Item -Recurse -Force $backupsDir; Write-Output "Backup-Ordner geloescht." }
        }
        if ($DeleteCerts) {
            $certsDir = Join-Path $ProjectDir "certs"
            if (Test-Path $certsDir) { Remove-Item -Recurse -Force $certsDir; Write-Output "Zertifikatsordner geloescht." }
        }
        $envPath = Join-Path $ProjectDir ".env"
        if (Test-Path $envPath) { Remove-Item -Force $envPath }
        Write-Output "Alle Daten wurden entfernt."
    } else {
        Write-Output "Daten (Datenbank, Bilder, Backups) wurden NICHT geloescht und bleiben erhalten."
    }
    Write-Output "Deinstallation abgeschlossen."
}

$sbRestore = {
    param($ProjectDir, $BackupZip)
    Set-Location $ProjectDir
    Write-Output "Spiele Komplett-Backup ein - ALLE aktuellen Daten werden ersetzt..."
    docker compose stop backend 2>&1 | Out-Null
    $dir = Split-Path -Parent $BackupZip
    $name = Split-Path -Leaf $BackupZip
    $dirDocker = $dir -replace "\\", "/"
    $py = @'
import zipfile, shutil, os
src = os.environ["SRC"]; data = "/app/data"; tmp = "/tmp/_restore"
shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
zipfile.ZipFile(src).extractall(tmp)
if os.path.exists(tmp + "/inventar.db"):
    shutil.copy(tmp + "/inventar.db", data + "/inventar.db")
for d in ("images", "branding"):
    s = tmp + "/" + d
    if os.path.isdir(s):
        os.makedirs(data + "/" + d, exist_ok=True)
        for f in os.listdir(s):
            shutil.copy(s + "/" + f, data + "/" + d + "/" + f)
print("Wiederherstellung abgeschlossen.")
'@
    docker compose run --rm --no-deps -T -e "SRC=/restore_src/$name" -v "${dirDocker}:/restore_src:ro" backend python -c $py 2>&1
    Write-Output "Starte Anwendung neu..."
    docker compose up -d 2>&1
    Write-Output "Komplett-Backup eingespielt. Die Anwendung wurde neu gestartet."
}

# ------------------------------------------------------------------
# Dialog: Erstinstallation (Formular fuer neue .env)
# ------------------------------------------------------------------
function Show-FreshInstallDialog {
    $dlg = New-Object System.Windows.Forms.Form
    $dlg.Text = "Erstinstallation"
    $dlg.Size = New-Object System.Drawing.Size(420, 500)
    $dlg.StartPosition = "CenterParent"
    $dlg.FormBorderStyle = "FixedDialog"
    $dlg.MaximizeBox = $false

    $yy = 15
    $mkLabel = {
        param($text, $ypos)
        $l = New-Object System.Windows.Forms.Label
        $l.Text = $text
        $l.Location = New-Object System.Drawing.Point(15, $ypos)
        $l.Size = New-Object System.Drawing.Size(370, 20)
        $dlg.Controls.Add($l)
    }

    & $mkLabel "Administrator-Benutzername:" $yy
    $yy += 22
    $txtUser = New-Object System.Windows.Forms.TextBox
    $txtUser.Text = "admin"
    $txtUser.Location = New-Object System.Drawing.Point(15, $yy)
    $txtUser.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtUser)
    $yy += 34

    & $mkLabel "Administrator-Passwort (leer = automatisch erzeugen):" $yy
    $yy += 22
    $txtPw = New-Object System.Windows.Forms.TextBox
    $txtPw.UseSystemPasswordChar = $true
    $txtPw.Location = New-Object System.Drawing.Point(15, $yy)
    $txtPw.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtPw)
    $yy += 34

    & $mkLabel "Port fuer die Weboberflaeche im lokalen Netz:" $yy
    $yy += 22
    $txtPort = New-Object System.Windows.Forms.TextBox
    $txtPort.Text = "8080"
    $txtPort.Location = New-Object System.Drawing.Point(15, $yy)
    $txtPort.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtPort)
    $yy += 34

    & $mkLabel "Port fuer HTTPS-Zugriff (Kamera-/Barcode-Scan):" $yy
    $yy += 22
    $txtTlsPort = New-Object System.Windows.Forms.TextBox
    $txtTlsPort.Text = "8443"
    $txtTlsPort.Location = New-Object System.Drawing.Point(15, $yy)
    $txtTlsPort.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtTlsPort)
    $yy += 34

    & $mkLabel "Verzeichnis fuer Backups:" $yy
    $yy += 22
    $txtBackup = New-Object System.Windows.Forms.TextBox
    $txtBackup.Text = "./backups"
    $txtBackup.Location = New-Object System.Drawing.Point(15, $yy)
    $txtBackup.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtBackup)
    $yy += 34

    & $mkLabel "Organisationsname (optional, erscheint in Kopfzeile/Login):" $yy
    $yy += 22
    $txtOrg = New-Object System.Windows.Forms.TextBox
    $txtOrg.Location = New-Object System.Drawing.Point(15, $yy)
    $txtOrg.Size = New-Object System.Drawing.Size(370, 24)
    $dlg.Controls.Add($txtOrg)
    $yy += 34

    & $mkLabel "Logo-Datei (optional, PNG/JPG/SVG/WEBP):" $yy
    $yy += 22
    $txtLogo = New-Object System.Windows.Forms.TextBox
    $txtLogo.Location = New-Object System.Drawing.Point(15, $yy)
    $txtLogo.Size = New-Object System.Drawing.Size(285, 24)
    $dlg.Controls.Add($txtLogo)
    $btnBrowse = New-Object System.Windows.Forms.Button
    $btnBrowse.Text = "Durchsuchen..."
    $btnBrowse.Location = New-Object System.Drawing.Point(305, $yy)
    $btnBrowse.Size = New-Object System.Drawing.Size(80, 24)
    $btnBrowse.Add_Click({
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Filter = "Bilder (*.png;*.jpg;*.jpeg;*.svg;*.webp)|*.png;*.jpg;*.jpeg;*.svg;*.webp"
        if ($ofd.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $txtLogo.Text = $ofd.FileName }
    })
    $dlg.Controls.Add($btnBrowse)
    $yy += 44

    $btnOk = New-Object System.Windows.Forms.Button
    $btnOk.Text = "Installieren"
    $btnOk.Location = New-Object System.Drawing.Point(190, $yy)
    $btnOk.Size = New-Object System.Drawing.Size(95, 30)
    $btnOk.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dlg.Controls.Add($btnOk)

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = "Abbrechen"
    $btnCancel.Location = New-Object System.Drawing.Point(290, $yy)
    $btnCancel.Size = New-Object System.Drawing.Size(95, 30)
    $btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dlg.Controls.Add($btnCancel)

    $dlg.AcceptButton = $btnOk
    $dlg.CancelButton = $btnCancel

    $result = $dlg.ShowDialog($form)
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) { return $null }

    $adminPw = $txtPw.Text
    if (-not $adminPw) {
        $pwBytes = New-Object byte[] 9
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pwBytes)
        $adminPw = [Convert]::ToBase64String($pwBytes) -replace "[/+=]", ""
    }

    return @{
        AdminUser = $(if ($txtUser.Text) { $txtUser.Text } else { "admin" })
        AdminPassword = $adminPw
        WebPort = $(if ($txtPort.Text) { $txtPort.Text } else { "8080" })
        WebTlsPort = $(if ($txtTlsPort.Text) { $txtTlsPort.Text } else { "8443" })
        BackupHostPath = $(if ($txtBackup.Text) { $txtBackup.Text } else { "./backups" })
        OrgName = $txtOrg.Text
        LogoPath = $txtLogo.Text
    }
}

# ------------------------------------------------------------------
# Dialog: Bereits installiert -> Update / Neuinstallation
# ------------------------------------------------------------------
function Show-UpdateChoiceDialog {
    $dlg = New-Object System.Windows.Forms.Form
    $dlg.Text = "Erstinstallation / Update"
    $dlg.Size = New-Object System.Drawing.Size(460, 320)
    $dlg.StartPosition = "CenterParent"
    $dlg.FormBorderStyle = "FixedDialog"
    $dlg.MaximizeBox = $false

    $lblInfo = New-Object System.Windows.Forms.Label
    $lblInfo.Text = "Es besteht bereits eine Installation.`r`nInstallierte Version: $(Get-InstalledVersion)`r`nVerfuegbare Version:  $(Get-AvailableVersion)"
    $lblInfo.Location = New-Object System.Drawing.Point(15, 15)
    $lblInfo.Size = New-Object System.Drawing.Size(420, 60)
    $dlg.Controls.Add($lblInfo)

    $rb1 = New-Object System.Windows.Forms.RadioButton
    $rb1.Text = "Update durchfuehren (Daten bleiben erhalten)"
    $rb1.Location = New-Object System.Drawing.Point(15, 90)
    $rb1.Size = New-Object System.Drawing.Size(420, 24)
    $rb1.Checked = $true
    $dlg.Controls.Add($rb1)

    $rb2 = New-Object System.Windows.Forms.RadioButton
    $rb2.Text = "Neuinstallation - Daten behalten (Container/Images komplett neu)"
    $rb2.Location = New-Object System.Drawing.Point(15, 120)
    $rb2.Size = New-Object System.Drawing.Size(420, 24)
    $dlg.Controls.Add($rb2)

    $rb3 = New-Object System.Windows.Forms.RadioButton
    $rb3.Text = "Neuinstallation - Daten LOESCHEN (Datenbank, Bilder, Verlauf weg)"
    $rb3.Location = New-Object System.Drawing.Point(15, 150)
    $rb3.Size = New-Object System.Drawing.Size(420, 24)
    $rb3.ForeColor = [System.Drawing.Color]::DarkRed
    $dlg.Controls.Add($rb3)

    $chkKeepBackups = New-Object System.Windows.Forms.CheckBox
    $chkKeepBackups.Text = "Backup-Ordner (.\backups) ebenfalls loeschen"
    $chkKeepBackups.Location = New-Object System.Drawing.Point(35, 178)
    $chkKeepBackups.Size = New-Object System.Drawing.Size(380, 24)
    $chkKeepBackups.Enabled = $false
    $dlg.Controls.Add($chkKeepBackups)

    $rb3.Add_CheckedChanged({ $chkKeepBackups.Enabled = $rb3.Checked })
    $rb1.Add_CheckedChanged({ if ($rb1.Checked) { $chkKeepBackups.Enabled = $false } })
    $rb2.Add_CheckedChanged({ if ($rb2.Checked) { $chkKeepBackups.Enabled = $false } })

    $btnOk = New-Object System.Windows.Forms.Button
    $btnOk.Text = "Weiter"
    $btnOk.Location = New-Object System.Drawing.Point(240, 220)
    $btnOk.Size = New-Object System.Drawing.Size(95, 30)
    $btnOk.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dlg.Controls.Add($btnOk)

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = "Abbrechen"
    $btnCancel.Location = New-Object System.Drawing.Point(340, 220)
    $btnCancel.Size = New-Object System.Drawing.Size(95, 30)
    $btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dlg.Controls.Add($btnCancel)

    $dlg.AcceptButton = $btnOk
    $dlg.CancelButton = $btnCancel

    $result = $dlg.ShowDialog($form)
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) { return $null }

    $choice = "update"
    if ($rb2.Checked) { $choice = "reinstall_keep" }
    if ($rb3.Checked) { $choice = "reinstall_delete" }

    return @{ Choice = $choice; DeleteBackups = $chkKeepBackups.Checked }
}

# ------------------------------------------------------------------
# Dialog: Deinstallation
# ------------------------------------------------------------------
function Show-UninstallDialog {
    $dlg = New-Object System.Windows.Forms.Form
    $dlg.Text = "Deinstallation"
    $dlg.Size = New-Object System.Drawing.Size(460, 300)
    $dlg.StartPosition = "CenterParent"
    $dlg.FormBorderStyle = "FixedDialog"
    $dlg.MaximizeBox = $false

    $lblInfo = New-Object System.Windows.Forms.Label
    $lblInfo.Text = "Die Anwendung wird gestoppt und entfernt. Bitte auswaehlen, was`r`nzusaetzlich geloescht werden soll:"
    $lblInfo.Location = New-Object System.Drawing.Point(15, 15)
    $lblInfo.Size = New-Object System.Drawing.Size(420, 40)
    $dlg.Controls.Add($lblInfo)

    $chkData = New-Object System.Windows.Forms.CheckBox
    $chkData.Text = "Alle Daten loeschen (Datenbank, Bilder, Artikel-Verlauf)"
    $chkData.Location = New-Object System.Drawing.Point(15, 65)
    $chkData.Size = New-Object System.Drawing.Size(420, 24)
    $chkData.ForeColor = [System.Drawing.Color]::DarkRed
    $dlg.Controls.Add($chkData)

    $chkBackups = New-Object System.Windows.Forms.CheckBox
    $chkBackups.Text = "Auch Backup-Ordner (.\backups) loeschen"
    $chkBackups.Location = New-Object System.Drawing.Point(35, 92)
    $chkBackups.Size = New-Object System.Drawing.Size(400, 24)
    $chkBackups.Enabled = $false
    $dlg.Controls.Add($chkBackups)

    $chkCerts = New-Object System.Windows.Forms.CheckBox
    $chkCerts.Text = "Auch HTTPS-Zertifikate (.\certs) loeschen"
    $chkCerts.Location = New-Object System.Drawing.Point(35, 118)
    $chkCerts.Size = New-Object System.Drawing.Size(400, 24)
    $chkCerts.Enabled = $false
    $dlg.Controls.Add($chkCerts)

    $chkData.Add_CheckedChanged({
        $chkBackups.Enabled = $chkData.Checked
        $chkCerts.Enabled = $chkData.Checked
    })

    $chkImages = New-Object System.Windows.Forms.CheckBox
    $chkImages.Text = "Auch gebaute Docker-Images entfernen (spart Speicherplatz)"
    $chkImages.Location = New-Object System.Drawing.Point(15, 150)
    $chkImages.Size = New-Object System.Drawing.Size(420, 24)
    $dlg.Controls.Add($chkImages)

    $btnOk = New-Object System.Windows.Forms.Button
    $btnOk.Text = "Deinstallieren"
    $btnOk.Location = New-Object System.Drawing.Point(230, 200)
    $btnOk.Size = New-Object System.Drawing.Size(105, 30)
    $btnOk.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $dlg.Controls.Add($btnOk)

    $btnCancel = New-Object System.Windows.Forms.Button
    $btnCancel.Text = "Abbrechen"
    $btnCancel.Location = New-Object System.Drawing.Point(340, 200)
    $btnCancel.Size = New-Object System.Drawing.Size(95, 30)
    $btnCancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $dlg.Controls.Add($btnCancel)

    $dlg.AcceptButton = $btnOk
    $dlg.CancelButton = $btnCancel

    $result = $dlg.ShowDialog($form)
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) { return $null }

    return @{
        RemoveVolumes = $chkData.Checked
        RemoveImages = $chkImages.Checked
        DeleteBackups = $chkBackups.Checked
        DeleteCerts = $chkCerts.Checked
    }
}

# ------------------------------------------------------------------
# Button-Ereignisse
# ------------------------------------------------------------------
$btnRefresh.Add_Click({ Update-StatusView })

$btnStart.Add_Click({
    if (-not (Test-Installed)) {
        [System.Windows.Forms.MessageBox]::Show("Es ist noch keine Installation vorhanden. Bitte zuerst 'Erweitert' -> 'Erstinstallation / Update' ausfuehren.", "Nicht installiert", "OK", "Warning") | Out-Null
        return
    }
    if (-not (Test-DockerReady)) {
        [System.Windows.Forms.MessageBox]::Show("Docker Desktop wurde nicht gefunden oder laeuft nicht. Bitte Docker Desktop starten und erneut versuchen.", "Docker nicht bereit", "OK", "Warning") | Out-Null
        return
    }
    Start-BackgroundAction $sbEnsureCert @($ProjectDir) {
        Start-BackgroundAction $sbStart @($ProjectDir) $null
    }
})

$btnStop.Add_Click({
    Start-BackgroundAction $sbStop @($ProjectDir) $null
})

$btnAdvancedToggle.Add_Click({
    $pnlAdvanced.Visible = -not $pnlAdvanced.Visible
    if ($pnlAdvanced.Visible) { $btnAdvancedToggle.Text = "Erweitert  <<" } else { $btnAdvancedToggle.Text = "Erweitert  >>" }
})

$btnInstallUpdate.Add_Click({
    $confirmResult = [System.Windows.Forms.MessageBox]::Show("Diesen Bereich wirklich oeffnen?", "Erstinstallation / Update", "YesNo", "Question")
    if ($confirmResult -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    if (-not (Test-DockerReady)) {
        [System.Windows.Forms.MessageBox]::Show("Docker Desktop wurde nicht gefunden oder laeuft nicht. Bitte Docker Desktop installieren/starten.", "Docker nicht bereit", "OK", "Warning") | Out-Null
        Start-Process "https://www.docker.com/products/docker-desktop/"
        return
    }

    if (-not (Test-Installed)) {
        $params = Show-FreshInstallDialog
        if (-not $params) { return }
        Start-BackgroundAction $sbFreshInstall @($ProjectDir, $params.AdminUser, $params.AdminPassword, $params.WebPort, $params.BackupHostPath, $params.WebTlsPort, $params.OrgName, $params.LogoPath) $null
        return
    }

    $choiceResult = Show-UpdateChoiceDialog
    if (-not $choiceResult) { return }

    switch ($choiceResult.Choice) {
        "update" {
            $c = [System.Windows.Forms.MessageBox]::Show("Update wirklich durchfuehren?", "Bestaetigung", "YesNo", "Question")
            if ($c -eq [System.Windows.Forms.DialogResult]::Yes) {
                Start-BackgroundAction $sbEnsureCert @($ProjectDir) {
                    Start-BackgroundAction $sbUpdateExisting @($ProjectDir) $null
                }
            }
        }
        "reinstall_keep" {
            $c = [System.Windows.Forms.MessageBox]::Show("Neuinstallation (Daten behalten) wirklich durchfuehren?", "Bestaetigung", "YesNo", "Question")
            if ($c -eq [System.Windows.Forms.DialogResult]::Yes) {
                Start-BackgroundAction $sbReinstallKeepData @($ProjectDir) $null
            }
        }
        "reinstall_delete" {
            $c = [System.Windows.Forms.MessageBox]::Show("WIRKLICH ALLE DATEN unwiderruflich loeschen und neu einrichten?", "ACHTUNG - Daten werden geloescht", "YesNo", "Warning")
            if ($c -eq [System.Windows.Forms.DialogResult]::Yes) {
                Start-BackgroundAction $sbReinstallDeleteData @($ProjectDir, $choiceResult.DeleteBackups) {
                    $params = Show-FreshInstallDialog
                    if ($params) {
                        Start-BackgroundAction $sbFreshInstall @($ProjectDir, $params.AdminUser, $params.AdminPassword, $params.WebPort, $params.BackupHostPath, $params.WebTlsPort, $params.OrgName, $params.LogoPath) $null
                    }
                }
            }
        }
    }
})

$btnUninstall.Add_Click({
    $confirmResult = [System.Windows.Forms.MessageBox]::Show("Diesen Bereich wirklich oeffnen?", "Deinstallation", "YesNo", "Question")
    if ($confirmResult -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    if (-not (Test-DockerReady)) {
        [System.Windows.Forms.MessageBox]::Show("Docker wurde nicht gefunden oder laeuft nicht - es laeuft vermutlich nichts mehr.", "Hinweis", "OK", "Information") | Out-Null
        return
    }

    $opts = Show-UninstallDialog
    if (-not $opts) { return }

    $c = [System.Windows.Forms.MessageBox]::Show("Anwendung wirklich stoppen und deinstallieren?", "Bestaetigung", "YesNo", "Warning")
    if ($c -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    Start-BackgroundAction $sbUninstall @($ProjectDir, $opts.RemoveVolumes, $opts.RemoveImages, $opts.DeleteBackups, $opts.DeleteCerts) $null
})

$btnRestore.Add_Click({
    if (-not (Test-Installed)) {
        [System.Windows.Forms.MessageBox]::Show("Es ist noch keine Installation vorhanden. Bitte zuerst 'Erstinstallation / Update' ausfuehren.", "Nicht installiert", "OK", "Warning") | Out-Null
        return
    }
    if (-not (Test-DockerReady)) {
        [System.Windows.Forms.MessageBox]::Show("Docker Desktop wurde nicht gefunden oder laeuft nicht. Bitte Docker Desktop starten und erneut versuchen.", "Docker nicht bereit", "OK", "Warning") | Out-Null
        return
    }

    $ofd = New-Object System.Windows.Forms.OpenFileDialog
    $ofd.Filter = "Komplett-Backup (*.zip)|*.zip"
    $ofd.Title = "Komplett-Backup zum Einspielen auswaehlen"
    if ($ofd.ShowDialog($form) -ne [System.Windows.Forms.DialogResult]::OK) { return }
    $zip = $ofd.FileName

    $c1 = [System.Windows.Forms.MessageBox]::Show("ALLE aktuellen Daten (Artikel, Personen/Benutzer, Einstellungen, Organisationsname, Logo, Status und Bilder) werden durch dieses Backup ERSETZT.`r`n`r`nFortfahren?", "Bist du sicher?", "YesNo", "Warning")
    if ($c1 -ne [System.Windows.Forms.DialogResult]::Yes) { return }
    $c2 = [System.Windows.Forms.MessageBox]::Show("Wirklich sicher? Diese Aktion kann NICHT rueckgaengig gemacht werden.", "Letzte Bestaetigung", "YesNo", "Warning")
    if ($c2 -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    Start-BackgroundAction $sbRestore @($ProjectDir, $zip) $null
})

$form.Add_Shown({ Update-StatusView })
$form.Add_FormClosing({
    if ($global:CurrentJob) {
        Stop-Job -Job $global:CurrentJob -ErrorAction SilentlyContinue
        Remove-Job -Job $global:CurrentJob -Force -ErrorAction SilentlyContinue
    }
})

[System.Windows.Forms.Application]::Run($form)
