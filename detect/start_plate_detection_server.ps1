# PowerShell script to start the plate detection server with proper setup

# Stop on errors
$ErrorActionPreference = "Stop"

# Define paths
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$envPath = Join-Path $scriptPath "aiplate_env"
$activateScript = Join-Path $envPath "Scripts\Activate.ps1"
$generateGrpcScript = Join-Path $scriptPath "generate_grpc.py"
$serverScript = Join-Path $scriptPath "plate_detection_service.py"

# Check if virtual environment exists
if (-not (Test-Path $activateScript)) {
    Write-Host "Error: Virtual environment not found at $envPath" -ForegroundColor Red
    Write-Host "Please create the virtual environment first." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting license plate detection server..." -ForegroundColor Cyan
Write-Host "Working directory: $scriptPath" -ForegroundColor Gray

# Activate the virtual environment
try {
    Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
    & $activateScript
    if ($LASTEXITCODE -ne 0) { throw "Failed to activate virtual environment" }
    
    # Generate gRPC code if needed
    if (Test-Path $generateGrpcScript) {
        Write-Host "Running gRPC code generation..." -ForegroundColor Yellow
        python $generateGrpcScript
        if ($LASTEXITCODE -ne 0) { throw "Failed to generate gRPC code" }
    } else {
        Write-Host "Warning: gRPC generation script not found at $generateGrpcScript" -ForegroundColor Yellow
    }
    
    # Start the server
    if (Test-Path $serverScript) {
        Write-Host "Starting plate detection server..." -ForegroundColor Green
        python $serverScript
        if ($LASTEXITCODE -ne 0) { throw "Server process exited with error code $LASTEXITCODE" }
    } else {
        throw "Server script not found at $serverScript"
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
