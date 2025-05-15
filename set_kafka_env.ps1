# Script to set KAFKA_HOME environment variable

Write-Host "Setting KAFKA_HOME Environment Variable" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host

# Check if KAFKA_HOME is already set
$currentKafkaHome = [Environment]::GetEnvironmentVariable('KAFKA_HOME', 'User')
if ($currentKafkaHome) {
    Write-Host "Current KAFKA_HOME is set to: $currentKafkaHome" -ForegroundColor Yellow
    $continue = Read-Host "Do you want to change it? (Y/N)"
    if ($continue -ne "Y" -and $continue -ne "y") {
        Write-Host "Exiting without changes." -ForegroundColor Green
        exit
    }
}

# Ask for Kafka installation path
Write-Host
Write-Host "Enter the full path to your Kafka installation:" -ForegroundColor Green
Write-Host "Example: C:\kafka" -ForegroundColor Gray
$kafkaPath = Read-Host "Path"

# Validate the path
if (-not (Test-Path $kafkaPath)) {
    Write-Host "ERROR: The specified directory does not exist!" -ForegroundColor Red
    Write-Host "Please download and extract Kafka first, then run this script again."
    exit
}

# Check for key Kafka files to validate the installation
$zookeeperScript = Join-Path $kafkaPath "bin\windows\zookeeper-server-start.bat"
$kafkaScript = Join-Path $kafkaPath "bin\windows\kafka-server-start.bat"

if (-not (Test-Path $zookeeperScript) -or -not (Test-Path $kafkaScript)) {
    Write-Host "ERROR: This does not appear to be a valid Kafka installation." -ForegroundColor Red
    Write-Host "Could not find required Kafka scripts in $kafkaPath\bin\windows" -ForegroundColor Red
    Write-Host "Please specify the root directory of your Kafka installation."
    exit
}

# Set the environment variable
try {
    [Environment]::SetEnvironmentVariable('KAFKA_HOME', $kafkaPath, 'User')
    Write-Host
    Write-Host "SUCCESS! KAFKA_HOME has been set to: $kafkaPath" -ForegroundColor Green
    Write-Host
    Write-Host "The change will take effect in new PowerShell/Command Prompt windows."
    Write-Host "For the current session, run:" -ForegroundColor Yellow
    Write-Host "`$env:KAFKA_HOME = `"$kafkaPath`""
    
    # Update the current session
    $env:KAFKA_HOME = $kafkaPath
    Write-Host
    Write-Host "Environment variable set for the current session."
    Write-Host
    Write-Host "Now you can run: ./kafka_tools.ps1 start"
} catch {
    Write-Host "ERROR: Failed to set environment variable: $_" -ForegroundColor Red
}
