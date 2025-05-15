# Vehicle Registration System - Implementation Summary

## Architecture Overview

This project implements a microservices architecture for a vehicle entry/exit system with the following components:

1. **CIN Extraction Service (Python, gRPC)**
   - Processes ID card images using OpenVINO and EasyOCR
   - Extracts personal information from ID cards
   - Exposes a gRPC API

2. **Plate Detection Service (Python, gRPC)**
   - Processes vehicle images to detect license plates
   - Uses computer vision techniques and OCR
   - Exposes a gRPC API

3. **Aggregator Service (Node.js, gRPC)**
   - Acts as a bridge between the API Gateway and microservices
   - Communicates with both services over gRPC
   - Combines results from both services
   - Exposes a gRPC API to the API Gateway

4. **API Gateway (Node.js, Express)**
   - Entry point for client applications
   - Exposes REST and GraphQL APIs
   - Serves the web client interface
   - Communicates with the Aggregator over gRPC

5. **Web Client (HTML, JavaScript, Bootstrap)**
   - User interface for security agents
   - Allows image upload for ID cards and vehicles
   - Displays extracted information and registration details

## Implementation Details

### gRPC Protocol Definitions
- Created proto files defining service interfaces
- Generated client and server code for both Python and JavaScript

### Microservice Implementation
- Implemented Python services with proper error handling and logging
- Created Node.js aggregator with unified error handling
- Used async/await patterns for clean code

### API Gateway Implementation
- Dual REST and GraphQL APIs
- File upload handling with multer
- Error handling and logging

### Web Client Implementation
- Responsive design with Bootstrap
- Real-time validation feedback
- Mobile-friendly interface

### Database Implementation
- MongoDB integration for persistent storage
- Mongoose ODM for schema validation and database operations
- Models for registrations and analytics
- Clean separation between data access and business logic
- RESTful API endpoints for CRUD operations
- GraphQL queries and mutations for flexible data access

## Starting the System

Use the `start_system.bat` script to launch all services at once.

## Testing

1. Open http://localhost:3000 in a browser
2. Upload an ID card image and a vehicle image
3. Select entry or exit registration
4. View the extracted information

## Architecture Patterns Used

- **Microservices Architecture**: System divided into small, independent services
- **API Gateway Pattern**: Single entry point for clients
- **Aggregator Pattern**: Combining data from multiple services
- **Multiple Protocols**: REST, GraphQL, and gRPC
- **Synchronous Communication**: Request-response pattern

## Future Work

- Add database persistence
- Implement Kafka for event-driven communication
  - Publish registration events when vehicles enter or exit
  - Create a registration events consumer service
  - Store historical registration data with timestamps
  - Enable real-time monitoring of vehicle movements
  - Support asynchronous processing for better scalability
- Add authentication and authorization
- Containerize services with Docker
