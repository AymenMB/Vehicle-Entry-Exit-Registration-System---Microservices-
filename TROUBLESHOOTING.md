# Troubleshooting Guide for Vehicle Entry/Exit Registration System

This document provides solutions for common issues you might encounter when running the Vehicle Entry/Exit Registration System.

## Common Issues and Solutions

### API Gateway Issues

1. Ensure the `uploads` directory exists in the API Gateway folder
   - Run `mkdir api_gateway\uploads` if it doesn't exist
   - The uploads directory is required for temporary file storage during image processing
   - Permission issues: Ensure the user running the application has write access to this directory

2. Connection Refused Errors
   - If you see "Impossible de se connecter au serveur distant" or "Connection refused" errors:
     - Check if the port 3000 is already in use by another application
     - Run `netstat -ano | findstr :3000` to check if the port is occupied
     - Kill the process with `taskkill /F /PID <process_id>` if needed
     - Try changing the port in `api_gateway\app.js` if the port conflict persists

3. File Access Issues
   - If you see "fichier est utilisé par un autre processus" (file is being used by another process):
     - Restart your system to release any locked files
     - Ensure no other instances of the application are running
     - Check if any antivirus software is scanning or locking files

### Microservices Connection Issues

1. gRPC Service Connection Problems
   - Ensure all services are running on their expected ports:
     - API Gateway: 3000
     - Aggregator: 50050
     - Plate Detection: 50051
     - CIN Extraction: 50052
   - Check service logs in the `logs` directory for specific error messages
   - Ensure the gRPC protocol buffers are properly compiled

2. Python Service Issues
   - Ensure the Python environment is activated: `.\aiplate_env\Scripts\activate`
   - Verify all Python dependencies are installed
   - Check if the OpenVINO runtime is properly set up (required for detection services)

### Kafka-Related Issues

1. Kafka Connection Problems
   - Ensure Kafka and Zookeeper are running
   - Check if KAFKA_HOME environment variable is properly set
   - Run `kafka_docker.bat status` or `kafka_dev_tools.bat list-topics` to verify Kafka status
   - If using Docker, check Docker container status with `docker ps`

2. Missing Kafka Topics
   - Create required topics using `kafka_docker.bat create-topics` or `kafka_dev_tools.bat create-topics`

### MongoDB Issues

1. MongoDB Connection Problems
   - Ensure MongoDB service is running:
     - Check in Windows Services (services.msc) if MongoDB service is running
     - Start it manually if not running: `Start-Service MongoDB`
     - If service doesn't exist, MongoDB may not be installed correctly
     - Run `install_mongodb.bat` to set up MongoDB properly
   
2. Database Access Issues
   - Ensure MongoDB is running on default port 27017
   - Check connection string in `.env` files in both `api_gateway` and `registration_consumer` directories
   - MongoDB uri format should be: `mongodb://localhost:27017/vehicle_registration_system`
   - Check logs for specific error messages (authentication failures, connection timeouts)

3. Data Not Being Saved
   - Ensure the applications have proper write permissions to the MongoDB data directory
   - Check disk space - MongoDB requires sufficient disk space for storage
   - Verify schema validation isn't rejecting records due to format issues
   - Check for unique constraint violations (e.g., duplicate registration IDs)

## Advanced Diagnostics

1. Run the diagnostic script for detailed system status:
   ```powershell
   .\diagnostic.ps1 > diagnostic_output.txt
   ```

2. Check individual service logs:
   ```
   logs\api_gateway.log
   logs\aggregator_service.log
   logs\cin_service.log
   logs\plate_service.log
   logs\registration_consumer.log
   ```

3. Test each service individually:
   - Start services one by one using the commands in `start_system.bat` or `start_system.ps1`
   - Check logs after starting each service to identify the problematic component

4. Network Port Issues:
   - Run `.\diagnostic.bat` to check port availability
   - Ensure no firewall rules are blocking the required ports

5. Verify directory structure:
   ```powershell
   # Check if all required directories exist
   Test-Path api_gateway\uploads
   Test-Path logs
   ```

## Quick Recovery Steps

1. Kill all running Node.js and Python processes:
   ```powershell
   taskkill /F /IM node.exe
   taskkill /F /IM python.exe
   ```

2. Delete temporary files:
   ```powershell
   Remove-Item -Recurse -Force api_gateway\uploads\*
   ```

3. Restart the system from scratch:
   ```powershell
   .\start_system.ps1
   ```

4. If all else fails, try a clean setup:
   ```powershell
   .\setup_environment.ps1
   .\start_system.ps1
   ```

## Contact Support

If you continue to experience issues, please file a ticket with logs attached.

### API Gateway Issues

#### API Gateway Fails to Start

If the API Gateway service fails to start or is not responding:

1. **Check the API Gateway logs**:
   ```
   cat logs\api_gateway.log
   cat logs\api_gateway_error.log
   ```

2. **Port conflict**: Verify if port 3000 is already in use:
   ```
   netstat -ano | findstr :3000
   ```
   If in use, either:
   - Kill the process: `taskkill /F /PID <process_id>`
   - Or change the API Gateway port in api_gateway\app.js

3. **Missing dependencies**: Ensure all dependencies are installed:
   ```
   cd api_gateway
   npm install
   ```

4. **Connection to Aggregator**: Check if the Aggregator service is running and the port is correct:
   ```
   cat aggregator\aggregator_port.txt
   ```
   This file contains the actual port where Aggregator is running.
   Ensure this port matches the one used in api_gateway\services\aggregator_client.js

5. **Restart API Gateway only**:
   ```
   cd api_gateway
   npm start
   ```

#### API Gateway Shows "ECONNREFUSED" Errors

This typically means the Aggregator service is not running or is using a different port:

1. Check if Aggregator is running:
   ```
   tasklist | findstr node
   ```

2. Check which port Aggregator is actually using:
   ```
   cat aggregator\aggregator_port.txt
   ```

3. Update the Aggregator port in the API Gateway's aggregator client:
   - Open api_gateway\services\aggregator_client.js
   - Update the port in the `SERVER_ADDRESS` variable

4. Restart both services:
   ```
   cd aggregator
   npm run start-service
   
   cd api_gateway
   npm start
   ```

#### API Gateway Kafka Connection Errors

If the API Gateway logs show Kafka connection errors:

1. Verify Kafka is running:
   ```
   kafka_docker.bat status
   ```
   or
   ```
   .\kafka_tools.ps1 list-topics
   ```

2. Check the kafka_config.js file is using the correct broker address

3. Try running the API Gateway with Kafka disabled:
   ```
   cd api_gateway
   $env:KAFKA_ENABLED="false"
   npm start
   ```

## Common Issues

### API Gateway Fails to Start

#### Missing Directories
   - Run `mkdir api_gateway\uploads` if it doesn't exist
   - Run `mkdir api_gateway\data` if it doesn't exist
   - Permission issues: Ensure the user running the application has write access to these directories

#### Connection Refused to localhost:3000
   - Check if the API Gateway process is running
   - Check logs\api_gateway_error.log for specific errors
   - Verify that no other application is using port 3000

### Kafka Connection Issues
   - Check if Kafka is running using `kafka_docker.bat status` or `kafka_dev_tools.bat check`
   - Ensure the required topics are created with `kafka_docker.bat create-topics`

### MongoDB Connection Issues
   - Ensure MongoDB is installed and the service is running
   - Check the connection string in the `.env` files
   - Verify MongoDB is running on the default port 27017
