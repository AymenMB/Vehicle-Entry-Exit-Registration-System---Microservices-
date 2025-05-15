# Vehicle Entry/Exit Registration System - Startup Instructions

This document provides detailed instructions for setting up and starting the Vehicle Entry/Exit Registration System, including the Kafka configuration.

## Prerequisites

1. Windows operating system
2. Node.js 14+ installed
3. Python 3.8+ (included in aiplate_env)
4. Apache Kafka 3.0+ (for event processing)

## Setup Steps

### 1. Set up the environment

Run the setup script to install all required dependencies:

**For CMD:**
```batch
setup_environment.bat
```

**For PowerShell:**
```powershell
.\setup_environment.bat
```

This will:
- Activate the Python virtual environment
- Install required Python packages
- Install Node.js dependencies for all services
- Generate gRPC code

### 2. Set up Kafka (Required for event processing)

#### a. Download and Install Kafka

1. Download Apache Kafka from [https://kafka.apache.org/downloads](https://kafka.apache.org/downloads)
2. Extract the downloaded archive to a directory of your choice (e.g., `C:\kafka`)
3. Set the KAFKA_HOME environment variable:

**For CMD:**
```batch
setx KAFKA_HOME "C:\kafka"
```

**For PowerShell:**
```powershell
[Environment]::SetEnvironmentVariable("KAFKA_HOME", "C:\kafka", "User")
```

> After setting environment variables, you may need to restart your terminal or PowerShell window.

#### b. Start Kafka Environment

**For CMD:**
```batch
kafka_dev_tools.bat start
```

**For PowerShell:**
```powershell
.\kafka_tools.ps1 start
# or
.\kafka_dev_tools.bat start
```

This will provide instructions for starting Zookeeper and Kafka in separate command prompts.

In the first command prompt:
```batch
%KAFKA_HOME%\bin\windows\zookeeper-server-start.bat %KAFKA_HOME%\config\zookeeper.properties
```

In the second command prompt:
```batch
%KAFKA_HOME%\bin\windows\kafka-server-start.bat %KAFKA_HOME%\config\server.properties
```

#### c. Create Required Kafka Topics

After Kafka is running, create the required topics:

**For CMD:**
```batch
kafka_dev_tools.bat create-topics
```

**For PowerShell:**
```powershell
.\kafka_tools.ps1 create-topics
# or
.\kafka_dev_tools.bat create-topics
```

This will create the following topics:
- vehicle-registrations
- system-notifications
- system-errors

Verify the topics were created:

**For CMD:**
```batch
kafka_dev_tools.bat list-topics
```

**For PowerShell:**
```powershell
.\kafka_tools.ps1 list-topics
# or
.\kafka_dev_tools.bat list-topics
```

### 3. Start the System

Use the startup script to start all services:

**For CMD:**
```batch
start_system.bat
```

**For PowerShell:**
```powershell
.\start_system.ps1
```

This will:
1. Start the CIN Extraction Service
2. Start the Plate Detection Service
3. Start the Aggregator Service
4. Start the Kafka Registration Consumer
5. Start the API Gateway
6. Open the web interface in your default browser

### 4. Verify the System

You can verify that all components are working correctly by running:

**For CMD:**
```batch
verify_system.bat
```

**For PowerShell:**
```powershell
.\verify_system.bat
```

Or by visiting these URLs in your browser:
- System status: http://localhost:3000/api/status
- Kafka status: http://localhost:3000/api/kafka_status

## Testing the System

1. Open the web interface at http://localhost:3000
2. Upload an ID card image and a vehicle image
3. Select "Entry Registration" or "Exit Registration"
4. Click "Process Registration"
5. View the extracted information
6. Check the "Registration History" sidebar to see past registrations

## Using the GraphQL API

The GraphQL API is available at http://localhost:3000/graphql

Sample GraphQL query:
```graphql
query {
  healthCheck
}
```

Sample GraphQL mutation for registration:
```graphql
mutation RegisterEntry($cinImage: Upload!, $vehicleImage: Upload!) {
  registerEntry(cinImage: $cinImage, vehicleImage: $vehicleImage) {
    success
    cinData {
      idNumber
      name
      lastname
    }
    plateData {
      plateNumber
      confidence
    }
    registrationId
    timestamp
    type
    error
  }
}
```

## Stopping the System

If using the startup script, press any key in the console window to stop all services.

If you started services manually, press Ctrl+C in each console window to stop each service.

To stop Kafka and Zookeeper, press Ctrl+C in their respective console windows.

## Troubleshooting

### Kafka Connection Issues

If you see "Failed to connect to Kafka" errors:

1. Verify Kafka is running by listing topics:
   ```
   .\kafka_tools.ps1 list-topics
   ```

2. Check if the KAFKA_HOME environment variable is set correctly:
   ```powershell
   echo $env:KAFKA_HOME
   ```

3. Ensure Kafka topics are created:
   ```
   .\kafka_tools.ps1 create-topics
   ```

4. Check the logs in the `logs` directory for any errors

### Service Starting Issues

If services fail to start:

1. Check if ports are already in use:
   ```
   netstat -ano | findstr :3000
   netstat -ano | findstr :50050
   netstat -ano | findstr :50051
   netstat -ano | findstr :50052
   ```

2. Kill any processes using those ports:
   ```
   taskkill /F /PID <process_id>
   ```

3. Try running the services individually to see specific errors
