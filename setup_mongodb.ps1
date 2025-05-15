# Setup MongoDB for Vehicle Entry/Exit Registration System
Write-Host "Setting up MongoDB for Vehicle Entry/Exit Registration System..." -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host

# Check if MongoDB is running
try {
    $mongoStatus = Get-Service -Name MongoDB -ErrorAction SilentlyContinue
    if ($mongoStatus -eq $null -or $mongoStatus.Status -ne "Running") {
        Write-Host "MongoDB service is not running. Attempting to start..." -ForegroundColor Yellow
        Start-Service -Name MongoDB -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "Could not start MongoDB service. Please ensure MongoDB is installed correctly." -ForegroundColor Red
    Write-Host "You can install MongoDB from: https://www.mongodb.com/try/download/community" -ForegroundColor Yellow
    exit 1
}

# Create database and collections using mongo shell
$mongoScript = @"
use vehicle_registration_system;

// Create registrations collection with validation
db.createCollection('registrations', {
  validator: {
    \$jsonSchema: {
      bsonType: 'object',
      required: ['registrationId', 'timestamp'],
      properties: {
        registrationId: {
          bsonType: 'string',
          description: 'must be a string and is required'
        },
        timestamp: {
          bsonType: ['string', 'date'],
          description: 'must be a string or date and is required'
        }
      }
    }
  }
});

// Create indexes
db.registrations.createIndex({ registrationId: 1 }, { unique: true });
db.registrations.createIndex({ timestamp: -1 });
db.registrations.createIndex({ 'plateData.plateNumber': 1 });
db.registrations.createIndex({ 'cinData.idNumber': 1 });
db.registrations.createIndex({ type: 1 });

print('Database setup completed successfully');
"@

# Save the script to a temporary file
$tempScript = [System.IO.Path]::GetTempFileName()
Set-Content -Path $tempScript -Value $mongoScript

# Run the script with mongosh or mongo
try {
    # Try with mongosh first (MongoDB 5.0+)
    mongosh --quiet --file $tempScript
} catch {
    try {
        # Fall back to mongo (older versions)
        mongo --quiet --file $tempScript
    } catch {
        Write-Host "Failed to execute MongoDB setup script. Please check if MongoDB tools are installed correctly." -ForegroundColor Red
        exit 1
    }
}

# Clean up temp file
Remove-Item $tempScript -Force

Write-Host "MongoDB setup completed successfully!" -ForegroundColor Green
Write-Host
Write-Host "The Vehicle Entry/Exit Registration System is now configured to use MongoDB." -ForegroundColor Green
Write-Host "You can start the application with 'run_system.bat'" -ForegroundColor Green
