# Script to ensure all required directories exist with proper permissions

Write-Host "Ensuring required directories exist..." -ForegroundColor Cyan

# List of required directories
$directories = @(
    @{Path="api_gateway\uploads"; Description="API Gateway file uploads"},
    @{Path="api_gateway\data"; Description="API Gateway data storage"},
    @{Path="logs"; Description="System logs"},
    @{Path="registration_consumer\db"; Description="Registration consumer database"}
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir.Path)) {
        Write-Host "Creating $($dir.Description) directory: $($dir.Path)" -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $dir.Path -Force | Out-Null
        
        if (Test-Path $dir.Path) {
            Write-Host "[SUCCESS] Created $($dir.Path)" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to create $($dir.Path)" -ForegroundColor Red
        }
    } else {
        Write-Host "[OK] $($dir.Description) directory exists: $($dir.Path)" -ForegroundColor Green
    }
    
    # Test write permission
    $testFile = Join-Path $dir.Path "permission_test.tmp"
    try {
        "test" | Out-File -FilePath $testFile -ErrorAction Stop
        Remove-Item -Path $testFile -Force -ErrorAction Stop
        Write-Host "       Write permissions OK" -ForegroundColor Green
    } catch {
        Write-Host "       [WARNING] Write permission issue detected for $($dir.Path)" -ForegroundColor Red
        Write-Host "       Error: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`nDirectory verification complete!" -ForegroundColor Cyan
Write-Host "If you continue to experience issues, try running this script as administrator." -ForegroundColor Yellow
