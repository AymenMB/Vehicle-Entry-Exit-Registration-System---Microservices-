# Complete Setup Guide for Vehicle Entry/Exit Registration System

This document provides a detailed guide for setting up and running the Vehicle Entry/Exit Registration System.

## Prerequisites

- Windows operating system
- Python 3.8+ (included in aiplate_env)
- Node.js 14+ (needs to be installed separately)
- npm (comes with Node.js)

## Directory Structure Setup

Ensure the following directory structure is in place:

```
vehicle-registration-system/
├── api_gateway/
│   ├── uploads/                  # Create this directory manually if missing
│   └── node_modules/             # Will be created during npm install
├── aggregator/
│   └── node_modules/             # Will be created during npm install
├── cin/                          # CIN extraction service
├── detect/                       # Plate detection service
├── registration_consumer/
│   └── node_modules/             # Will be created during npm install
├── logs/                         # Create this directory manually if missing
├── setup_environment.bat
└── setup_environment.ps1
```

Create required directories if they don't exist:
```powershell
# Create directories (run in PowerShell)
mkdir -Force api_gateway\uploads
mkdir -Force logs
```

```batch
REM Create directories (run in Command Prompt)
mkdir api_gateway\uploads
mkdir logs
```

## Setup Process

Follow these steps to set up the system:

### 1. Prepare the Environment

The system uses the `aiplate_env` virtual environment which is already included in the project.

### 2. Run the Setup Script

Run the setup script to install all dependencies:

```batch
# For Windows CMD
setup_environment.bat

# For PowerShell
.\setup_environment.ps1
```

This script will:
- Activate the aiplate_env environment
- Install Python dependencies from requirements.txt
- Install Node.js dependencies for the aggregator service
- Install Node.js dependencies for the API gateway

### 3. Regenerate gRPC Code (if needed)

If you encounter any gRPC-related issues, regenerate the gRPC code:

```batch
# For Windows CMD
regenerate_grpc.bat

# For PowerShell
.\regenerate_grpc.ps1
```

### 4. Start the System

Start all services using the provided script:

```batch
# For Windows CMD
start_system.bat

# For PowerShell
.\start_system.ps1
```

This will start:
1. CIN Extraction Service (Python)
2. Plate Detection Service (Python)
3. Aggregator Service (Node.js)
4. API Gateway (Node.js)

### 5. Access the System

Once all services are running:
- Web Interface: http://localhost:3000
- GraphQL API: http://localhost:3000/graphql
- REST API: http://localhost:3000/api

## Troubleshooting

If you encounter issues:

1. Check log files in the `logs` directory
2. Ensure all required dependencies are installed correctly
3. Make sure the aiplate_env is activated when running Python services
4. Verify that Node.js and npm are installed and working properly

For environment-specific issues:
- All Python code runs within the `aiplate_env` virtual environment
- Models are loaded from their respective directories within `cin/model/` and `detect/model_platecar/`

## Component Details

- **API Gateway**: Express.js server with REST and GraphQL endpoints
- **Aggregator**: Node.js service that coordinates between microservices
- **CIN Extraction**: Python service for ID card information extraction
- **Plate Detection**: Python service for license plate recognition

Each component has its own configuration and dependencies managed through the setup scripts.
