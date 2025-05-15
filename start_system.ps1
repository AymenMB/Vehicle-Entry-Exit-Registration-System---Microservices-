# Start script for Vehicle Entry/Exit Registration System
Write-Host "Starting Vehicle Entry/Exit Registration System..." -ForegroundColor Green

# Check Kafka environment variable
if (-not (Test-Path env:KAFKA_HOME)) {
    Write-Host "WARNING: KAFKA_HOME environment variable is not set." -ForegroundColor Yellow
    Write-Host "Kafka functionality may not work properly."
    Write-Host "To set KAFKA_HOME, run: setx KAFKA_HOME 'C:\kafka'"
    Write-Host ""
} else {
    Write-Host "Using Kafka installation from: $env:KAFKA_HOME" -ForegroundColor Cyan
}

# Create logs directory if it doesn't exist
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Activate the Python environment
& "$PSScriptRoot\aiplate_env\Scripts\Activate.ps1"

# Start CIN Extraction Service
Write-Host "Starting CIN Extraction Service..." -ForegroundColor Cyan
$cinProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", "cd cin; python cin_extraction_service.py" -RedirectStandardOutput "$PSScriptRoot\logs\cin_service.log" -RedirectStandardError "$PSScriptRoot\logs\cin_service_error.log" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

# Start Plate Detection Service
Write-Host "Starting Plate Detection Service..." -ForegroundColor Cyan
$plateProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", "cd detect; python plate_detection_service.py" -RedirectStandardOutput "$PSScriptRoot\logs\plate_service.log" -RedirectStandardError "$PSScriptRoot\logs\plate_service_error.log" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

# Install Node.js dependencies if not already installed
Write-Host "Checking Node.js dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "aggregator\node_modules")) {
    Write-Host "Installing Aggregator dependencies..." -ForegroundColor Yellow
    Push-Location aggregator
    npm install
    Pop-Location
}
if (-not (Test-Path "api_gateway\node_modules")) {
    Write-Host "Installing API Gateway dependencies..." -ForegroundColor Yellow
    Push-Location api_gateway
    npm install
    Pop-Location
}
if (-not (Test-Path "registration_consumer\node_modules")) {
    Write-Host "Installing Registration Consumer dependencies..." -ForegroundColor Yellow
    Push-Location registration_consumer
    npm install
    Pop-Location
}

# Start Aggregator Service
Write-Host "Starting Aggregator Service..." -ForegroundColor Cyan
$aggregatorProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", "cd aggregator; npm run start-service" -RedirectStandardOutput "$PSScriptRoot\logs\aggregator_service.log" -RedirectStandardError "$PSScriptRoot\logs\aggregator_service_error.log" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

# Start Kafka Registration Consumer Service
Write-Host "Starting Kafka Registration Consumer Service..." -ForegroundColor Cyan
$consumerProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", "cd registration_consumer; npm start" -RedirectStandardOutput "$PSScriptRoot\logs\registration_consumer.log" -RedirectStandardError "$PSScriptRoot\logs\registration_consumer_error.log" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

# Start API Gateway
Write-Host "Starting API Gateway..." -ForegroundColor Cyan
$apiGatewayProcess = Start-Process -FilePath "powershell.exe" -ArgumentList "-Command", "cd api_gateway; npm start" -RedirectStandardOutput "$PSScriptRoot\logs\api_gateway.log" -RedirectStandardError "$PSScriptRoot\logs\api_gateway_error.log" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

Write-Host "All services started!" -ForegroundColor Green
Write-Host "API Gateway running at http://localhost:3000" -ForegroundColor Cyan
Write-Host "GraphQL API available at http://localhost:3000/graphql" -ForegroundColor Cyan
Write-Host "Kafka events being processed by Registration Consumer" -ForegroundColor Cyan
Write-Host ""
Write-Host "To verify system status, visit: http://localhost:3000/api/status" -ForegroundColor Yellow
Write-Host "To verify Kafka status, visit: http://localhost:3000/api/kafka_status" -ForegroundColor Yellow
Write-Host ""

# Open the web interface
Start-Process "http://localhost:3000"

Write-Host "Press any key to stop all services..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Kill all the services when any key is pressed
Write-Host "Stopping all services..." -ForegroundColor Red
Stop-Process -Id $cinProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $plateProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $aggregatorProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $apiGatewayProcess.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $consumerProcess.Id -Force -ErrorAction SilentlyContinue

Write-Host "Services stopped." -ForegroundColor Green

# Deactivate the Python environment
deactivate
