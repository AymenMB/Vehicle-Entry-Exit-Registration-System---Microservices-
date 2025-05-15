# PowerShell script to start the plate detection server

# Stop on errors
$ErrorActionPreference = "Stop"

# Define paths
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$envPath = Join-Path $scriptPath "aiplate_env"
$activateScript = Join-Path $envPath "Scripts\\Activate.ps1" # Use double backslash for literal
$pythonExecutable = Join-Path $envPath "Scripts\\python.exe" # Use the venv python
$generateGrpcScript = Join-Path $scriptPath "generate_grpc.py"
$serverScript = Join-Path $scriptPath "plate_detection_service.py"
$protosDir = Join-Path $scriptPath "protos"
$initPyPath = Join-Path $protosDir "__init__.py"

# Check if virtual environment exists
if (-not (Test-Path $activateScript)) {
    Write-Host "Error: Virtual environment not found at $envPath" -ForegroundColor Red
    Write-Host "Please create the virtual environment first (e.g., python -m venv aiplate_env)." -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting license plate detection server..." -ForegroundColor Cyan
Write-Host "Working directory: $scriptPath" -ForegroundColor Gray

# Activate the virtual environment and run commands within it
try {
    Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
    # Activate by dot-sourcing
    . $activateScript

    # Ensure protos directory exists
    if (-not (Test-Path $protosDir)) {
        New-Item -ItemType Directory -Path $protosDir | Out-Null
        Write-Host "Created protos directory." -ForegroundColor Green
    }

    # Ensure __init__.py exists in protos directory
    if (-not (Test-Path $initPyPath)) {
        New-Item -ItemType File -Path $initPyPath | Out-Null
        Write-Host "Created __init__.py in protos directory." -ForegroundColor Green
    }

    # Generate gRPC code using the dedicated script
    Write-Host "Running gRPC code generation..." -ForegroundColor Yellow
    if (Test-Path $generateGrpcScript) {
        & $pythonExecutable $generateGrpcScript # Use the venv python
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error during gRPC code generation script execution." -ForegroundColor Red
            throw "gRPC code generation failed"
        }
        Write-Host "gRPC code generation script completed." -ForegroundColor Green
    } else {
        Write-Host "Error: gRPC generation script not found at $generateGrpcScript" -ForegroundColor Red
        throw "Missing gRPC generation script"
    }

    # Start the server
    Write-Host "Starting plate detection server ($($serverScript))..." -ForegroundColor Yellow
    if (Test-Path $serverScript) {
        & $pythonExecutable $serverScript # Use the venv python
    } else {
        Write-Host "Error: Server script not found at $serverScript" -ForegroundColor Red
        throw "Missing server script"
    }
} catch {
    Write-Host "An error occurred: $($_.Exception.Message)" -ForegroundColor Red
    # Attempt to deactivate if possible
    try { deactivate } catch {}
    exit 1
} finally {
    # Ensure deactivation happens even if the server is stopped manually (Ctrl+C)
    # Note: This might not always run if the script is terminated abruptly
    Write-Host "Deactivating virtual environment..." -ForegroundColor Gray
    try { deactivate } catch {}
}
