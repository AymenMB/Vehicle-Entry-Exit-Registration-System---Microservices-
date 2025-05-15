# Kafka management tools for PowerShell

param (
    [Parameter(Position=0, Mandatory=$true)]
    [ValidateSet("start", "stop", "list-topics", "create-topics", "help", "check")]
    [string]$Command
)

function Show-Usage {
    Write-Host "Kafka Management Tools" -ForegroundColor Cyan
    Write-Host "=====================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\kafka_tools.ps1 start        - Start Kafka and Zookeeper"
    Write-Host "  .\kafka_tools.ps1 stop         - Stop Kafka and Zookeeper"
    Write-Host "  .\kafka_tools.ps1 list-topics  - List all Kafka topics"
    Write-Host "  .\kafka_tools.ps1 create-topics - Create required topics"
    Write-Host "  .\kafka_tools.ps1 check        - Check Kafka environment"
    Write-Host "  .\kafka_tools.ps1 help         - Show this help message"
    Write-Host ""
    Write-Host "For Kafka setup assistance, run kafka_setup.bat" -ForegroundColor Green
    Write-Host ""
}

function Check-KafkaHome {
    if (-not $env:KAFKA_HOME) {
        Write-Host "Error: KAFKA_HOME environment variable is not set." -ForegroundColor Red
        Write-Host "Please set it to your Kafka installation directory using:"
        Write-Host "  [Environment]::SetEnvironmentVariable('KAFKA_HOME', 'C:\kafka', 'User')"
        Write-Host ""
        Write-Host "For easier setup, run kafka_setup.bat" -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    # Check if KAFKA_HOME exists and contains the required files
    if (-not (Test-Path $env:KAFKA_HOME)) {
        Write-Host "Error: KAFKA_HOME directory does not exist: $env:KAFKA_HOME" -ForegroundColor Red
        Write-Host "Please update it to a valid Kafka installation directory."
        Write-Host "For easier setup, run kafka_setup.bat" -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    $zookeeperScript = Join-Path $env:KAFKA_HOME "bin\windows\zookeeper-server-start.bat"
    $kafkaScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-server-start.bat"
    
    if (-not (Test-Path $zookeeperScript) -or -not (Test-Path $kafkaScript)) {
        Write-Host "Error: Kafka installation appears to be invalid." -ForegroundColor Red
        Write-Host "Cannot find required scripts in $env:KAFKA_HOME\bin\windows"
        Write-Host "For easier setup, run kafka_setup.bat" -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    return $true
}

function Start-Kafka {
    if (-not (Check-KafkaHome)) { return }
    
    Write-Host "Starting Zookeeper and Kafka..." -ForegroundColor Green
    Write-Host ""
    
    # Get absolute paths to the scripts
    $zookeeperScript = Join-Path $env:KAFKA_HOME "bin\windows\zookeeper-server-start.bat"
    $zookeeperConfig = Join-Path $env:KAFKA_HOME "config\zookeeper.properties"
    
    $kafkaScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-server-start.bat"
    $kafkaConfig = Join-Path $env:KAFKA_HOME "config\server.properties"
    
    Write-Host "In one PowerShell window, run:" -ForegroundColor Cyan
    Write-Host "  & `"$zookeeperScript`" `"$zookeeperConfig`""
    Write-Host ""
    Write-Host "In another PowerShell window, run:" -ForegroundColor Cyan
    Write-Host "  & `"$kafkaScript`" `"$kafkaConfig`""
    Write-Host ""
    Write-Host "After both are running, run the following to create the required topics:" -ForegroundColor Yellow
    Write-Host "  .\kafka_tools.ps1 create-topics"
    Write-Host ""
    
    # Alternative with direct command examples
    Write-Host "Alternative commands:" -ForegroundColor Magenta
    Write-Host "cd $env:KAFKA_HOME" -ForegroundColor White
    Write-Host "bin\windows\zookeeper-server-start.bat config\zookeeper.properties" -ForegroundColor White
    Write-Host "bin\windows\kafka-server-start.bat config\server.properties" -ForegroundColor White
    Write-Host ""
}

function Stop-Kafka {
    Write-Host "Stopping Kafka and Zookeeper..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run these commands in the PowerShell windows where Kafka and Zookeeper are running:" -ForegroundColor Cyan
    Write-Host "  Press Ctrl+C to stop the processes."
    Write-Host ""
}

function List-KafkaTopics {
    if (-not (Check-KafkaHome)) { return }
    
    Write-Host "Listing Kafka topics..." -ForegroundColor Green
    try {
        $topicsScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-topics.bat"
        & $topicsScript --list --bootstrap-server localhost:9092
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "Error: Failed to list topics." -ForegroundColor Red
            Write-Host "Make sure Kafka and Zookeeper are running." -ForegroundColor Yellow
            Write-Host "Run '.\kafka_tools.ps1 start' to start them." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Error listing topics: $_" -ForegroundColor Red
        Write-Host "Make sure Kafka and Zookeeper are running." -ForegroundColor Yellow
    }
}

function Create-KafkaTopics {
    if (-not (Check-KafkaHome)) { return }
    
    Write-Host "Creating required Kafka topics..." -ForegroundColor Green
    
    $topicsScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-topics.bat"
    
    Write-Host "Creating 'vehicle-registrations' topic..." -ForegroundColor Cyan
    try {
        & $topicsScript --create --topic vehicle-registrations --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error creating vehicle-registrations topic." -ForegroundColor Red
            Write-Host "Make sure Kafka and Zookeeper are running." -ForegroundColor Yellow
            Write-Host "If the topic already exists, you can ignore this error." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Error creating vehicle-registrations topic: $_" -ForegroundColor Red
    }
    
    Write-Host "Creating 'system-notifications' topic..." -ForegroundColor Cyan
    try {
        & $topicsScript --create --topic system-notifications --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error creating system-notifications topic." -ForegroundColor Red
            Write-Host "Make sure Kafka and Zookeeper are running." -ForegroundColor Yellow
            Write-Host "If the topic already exists, you can ignore this error." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Error creating system-notifications topic: $_" -ForegroundColor Red
    }
    
    Write-Host "Creating 'system-errors' topic..." -ForegroundColor Cyan
    try {
        & $topicsScript --create --topic system-errors --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error creating system-errors topic." -ForegroundColor Red
            Write-Host "Make sure Kafka and Zookeeper are running." -ForegroundColor Yellow
            Write-Host "If the topic already exists, you can ignore this error." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Error creating system-errors topic: $_" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Verifying topics were created:" -ForegroundColor Green
    List-KafkaTopics
    
    Write-Host ""
    Write-Host "Topics configuration completed." -ForegroundColor Green
}

function Check-KafkaEnvironment {
    Write-Host "Checking Kafka environment..." -ForegroundColor Green
    
    if (-not $env:KAFKA_HOME) {
        Write-Host "KAFKA_HOME environment variable is not set." -ForegroundColor Red
        Write-Host "Please run kafka_setup.bat for setup instructions." -ForegroundColor Yellow
        return
    }
    
    Write-Host "KAFKA_HOME is set to: $env:KAFKA_HOME" -ForegroundColor Cyan
    
    if (-not (Test-Path $env:KAFKA_HOME)) {
        Write-Host "ERROR: The directory does not exist!" -ForegroundColor Red
        Write-Host "Please run kafka_setup.bat to fix this issue." -ForegroundColor Yellow
        return
    }
    
    $zookeeperScript = Join-Path $env:KAFKA_HOME "bin\windows\zookeeper-server-start.bat"
    $kafkaScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-server-start.bat"
    $topicsScript = Join-Path $env:KAFKA_HOME "bin\windows\kafka-topics.bat"
    
    if (-not (Test-Path $zookeeperScript)) {
        Write-Host "ERROR: Zookeeper script not found at: $zookeeperScript" -ForegroundColor Red
        Write-Host "Please run kafka_setup.bat to fix this issue." -ForegroundColor Yellow
    } else {
        Write-Host "Zookeeper script found: $zookeeperScript" -ForegroundColor Green
    }
    
    if (-not (Test-Path $kafkaScript)) {
        Write-Host "ERROR: Kafka script not found at: $kafkaScript" -ForegroundColor Red
        Write-Host "Please run kafka_setup.bat to fix this issue." -ForegroundColor Yellow
    } else {
        Write-Host "Kafka script found: $kafkaScript" -ForegroundColor Green
    }
    
    if (-not (Test-Path $topicsScript)) {
        Write-Host "ERROR: Kafka topics script not found at: $topicsScript" -ForegroundColor Red
        Write-Host "Please run kafka_setup.bat to fix this issue." -ForegroundColor Yellow
    } else {
        Write-Host "Kafka topics script found: $topicsScript" -ForegroundColor Green
    }
    
    # Check if Kafka is running
    try {
        & $topicsScript --list --bootstrap-server localhost:9092 --command-config "$env:KAFKA_HOME\config\command.properties" 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Kafka is currently running!" -ForegroundColor Green
        } else {
            Write-Host "Kafka is not running." -ForegroundColor Yellow
            Write-Host "To start Kafka, run: .\kafka_tools.ps1 start" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "Kafka is not running." -ForegroundColor Yellow
        Write-Host "To start Kafka, run: .\kafka_tools.ps1 start" -ForegroundColor Cyan
    }
}

# Main switch for commands
switch ($Command) {
    "start" { Start-Kafka }
    "stop" { Stop-Kafka }
    "list-topics" { List-KafkaTopics }
    "create-topics" { Create-KafkaTopics }
    "check" { Check-KafkaEnvironment }
    "help" { Show-Usage }
    default { Show-Usage }
}
