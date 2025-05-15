# Testing the Vehicle Entry/Exit Registration System

This document provides instructions for testing the different components and functionalities of the Vehicle Entry/Exit Registration System.

## Prerequisites

1. Ensure all services are running (use `.\start_system.ps1` or `start_system.bat`)
2. Have test images ready for CIN cards and vehicle license plates
3. Check that the correct ports are being used (3000 for API Gateway, 50050 for Aggregator, 50051 for Plate Detection, 50052 for CIN Extraction)
4. Verify Kafka is running (if required for your test scenario)

## Testing Steps

### 1. Check System Status

1. Run the status check script:
   ```powershell
   .\check_status.ps1
   ```

2. Verify all services are reporting as running
   - If any service shows [ERROR], check the corresponding logs in the `logs` directory

3. Access the status API endpoint directly:
   ```
   http://localhost:3000/api/status
   ```

### 2. Test API Gateway Connectivity

1. Access the web interface:
   ```
   http://localhost:3000
   ```

2. If the web interface doesn't load:
   - Check if the API Gateway service is running
   - Verify port 3000 is not used by another application
   - Check the `logs/api_gateway.log` file for errors

3. Test the health endpoint:
   ```
   http://localhost:3000/health
   ```

### 3. Test Image Processing

1. Use the web interface to upload test images
   - For CIN: Use a sample ID card image
   - For Vehicle: Use a sample license plate image

2. Alternative: Test via REST API using curl:
   ```bash
   curl -X POST http://localhost:3000/api/cin/extract -F "image=@test_cin.jpg"
   curl -X POST http://localhost:3000/api/plate/detect -F "image=@test_plate.jpg"
   ```

3. Check the response for valid data extraction

### 4. Test Registration Process

1. Complete a full registration cycle (entry and exit)
2. Verify registration IDs are generated
3. Check Kafka events (if enabled) using:
   ```
   .\kafka_tools.ps1 consume-messages
   # or
   .\kafka_docker.bat consume vehicle-registrations
   ```

### 5. Test GraphQL API

1. Access the GraphQL playground:
   ```
   http://localhost:3000/graphql
   ```

2. Run a test query:
   ```graphql
   query {
     healthCheck
   }
   ```

## Troubleshooting Test Failures

1. Check logs in the `logs` directory for detailed error messages
2. Verify all required directories exist (especially `api_gateway/uploads`)
3. Ensure no port conflicts with other applications
4. Check that all services are running using `.\check_status.ps1`
5. For more detailed troubleshooting, refer to the `TROUBLESHOOTING.md` guide

## Automated Testing

Run the verification script to perform basic system checks:
```powershell
.\verify_system.ps1
```

This will test:
- Service connectivity
- API endpoints
- Basic functionality
- Kafka connectivity (if enabled)
