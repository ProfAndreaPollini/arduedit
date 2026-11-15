# setup_laboratorio.ps1 - Eseguire come Amministratore
$ErrorActionPreference = "Stop"

# --- 1. Percorsi ---
$GlobalArduinoDataDir = "C:\ProgramData\ArduinoData"
# Sorgente dell'exe: può essere un'installazione già presente,
# un file scaricato a parte, o il vendor del progetto ArduEdit
$ArduinoCliSource = "vendor\arduino-cli.exe"   # ← adatta questo percorso

# --- 2. Cartella condivisa + permessi ---
if (-not (Test-Path $GlobalArduinoDataDir)) {
    New-Item -ItemType Directory -Path $GlobalArduinoDataDir -Force | Out-Null
}
$Acl = Get-Acl $GlobalArduinoDataDir
$Rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "Users", "FullControl", "ContainerInherit, ObjectInherit", "None", "Allow")
$Acl.SetAccessRule($Rule)
Set-Acl $GlobalArduinoDataDir $Acl
Write-Host "Cartella pronta: $GlobalArduinoDataDir"

# --- 3. Variabile d'ambiente di sistema ---
[Environment]::SetEnvironmentVariable(
    "ARDUINO_DIRECTORIES_DATA", $GlobalArduinoDataDir, "Machine")
Write-Host "ARDUINO_DIRECTORIES_DATA impostata a livello di sistema"

# --- 4. Copia arduino-cli.exe nella cartella condivisa ---
if (-not (Test-Path $ArduinoCliSource)) {
    Write-Error "arduino-cli.exe non trovato in $ArduinoCliSource"
    exit 1
}
Copy-Item -Path $ArduinoCliSource -Destination "$GlobalArduinoDataDir\arduino-cli.exe" -Force
Write-Host "arduino-cli.exe copiato in $GlobalArduinoDataDir"

# --- 5. Installazione core (usa l'exe appena copiato + la env var appena impostata) ---
$ArduinoCli = "$GlobalArduinoDataDir\arduino-cli.exe"

$env:ARDUINO_DIRECTORIES_DATA = $GlobalArduinoDataDir
Write-Host "Installazione core Arduino AVR..."
& $ArduinoCli core install arduino:avr


$env:ARDUINO_DIRECTORIES_DATA = $GlobalArduinoDataDir
# Esempio ESP32 (opzionale)
# Write-Host "Installazione core ESP32..."
& $ArduinoCli --additional-urls "https://espressif.github.io/arduino-esp32/package_esp32_index.json" core install esp32:esp32

Write-Host "Setup completato."