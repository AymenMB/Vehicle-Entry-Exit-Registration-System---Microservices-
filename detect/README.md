<!-- filepath: d:\\ISIMM_PFE\\parking\\detect\\README.md -->
# License Plate Detection gRPC Microservice

This component is a dedicated microservice responsible for license plate detection from vehicle images. It utilizes an OpenVINO-based model and exposes its functionality via a gRPC interface.

## Overview

The microservice is designed for efficient and accurate license plate recognition. It receives an image, processes it using a machine learning model, and returns the detected plate number along with a confidence score.

**Key Features:**
- **gRPC Interface**: Provides a high-performance, language-agnostic communication protocol. Defined in `protos/plate_detection.proto`.
- **OpenVINO Model**: Leverages Intel's OpenVINO toolkit for optimized deep learning inference.
- **Python Implementation**: The service is built in Python.
- **Virtual Environment**: Uses a dedicated Python virtual environment (`aiplate_env`) to manage dependencies.

## Directory Structure

- `plate_detection_service.py`: The gRPC server implementation that hosts the plate detection model.
- `plate_detection_client.py`: A gRPC client for testing the service directly.
- `generate_grpc.py`: Script to generate Python gRPC stubs from the `.proto` definition.
- `protos/`: Contains the Protocol Buffer definition (`plate_detection.proto`) and the generated Python gRPC files.
  - `plate_detection.proto`: Defines the service, request, and response messages for gRPC communication.
  - `plate_detection_pb2.py`: Generated Python code for message serialization/deserialization.
  - `plate_detection_pb2_grpc.py`: Generated Python code for gRPC client and server stubs.
- `aiplate_env/`: Python virtual environment with all necessary dependencies (e.g., `grpcio`, `opencv-python`, `openvino`).
- `model_platecar/`, `plate_ex/`: Directories containing the machine learning model files and metadata.
- `run_plate_client.bat`: Batch script to easily run the test client.
- `start_plate_detection_server.ps1`: PowerShell script to start the gRPC server, ensuring the virtual environment is activated.

## gRPC Service Definition (`plate_detection.proto`)

The service is defined as follows:

```protobuf
// ...
service PlateDetectionService {
  // Send a car image and receive plate detection results
  rpc DetectPlate (PlateRequest) returns (PlateResponse) {}
}

message PlateRequest {
  bytes image = 1;  // The image as bytes
  string filename = 2;  // Original filename (optional)
}

message PlateResponse {
  string plate_number = 1;  // The detected plate number
  float confidence = 2;  // Confidence score
  string error_message = 3;  // Error message if any
  bool success = 4;  // Whether the detection was successful
}
// ...
```

## How to Use

### 1. Prerequisites
- Ensure Python is installed.
- Ensure the `aiplate_env` virtual environment is created and all dependencies from `requirements.txt` (if available, otherwise install manually: `grpcio`, `grpcio-tools`, `opencv-python`, `openvino`, `numpy`, `easyocr`, etc.) are installed.

### 2. Generate gRPC Code (if needed)
If you modify `protos/plate_detection.proto`, regenerate the Python gRPC code:
```powershell
# Activate the virtual environment
.\aiplate_env\Scripts\Activate.ps1
# Navigate to the detect directory
cd d:\ISIMM_PFE\parking\detect
# Run the generation script
python generate_grpc.py
```

### 3. Starting the gRPC Server
```powershell
# From the 'detect' directory (d:\ISIMM_PFE\parking\detect)
.\start_plate_detection_server.ps1
```
This script will activate the virtual environment and start `plate_detection_service.py`. The server will listen on a configured port (e.g., 50051).

### 4. Testing the Service (Optional)
You can test the gRPC service directly using `plate_detection_client.py`:
```powershell
# Make sure the server is running in another terminal
# From the 'detect' directory (d:\ISIMM_PFE\parking\detect)
.\run_plate_client.bat your_image.jpg
```
Replace `your_image.jpg` with the path to an image file. The client will output the detection result in JSON format.

## Integration with the Main Application

This gRPC microservice is consumed by the main Next.js application (specifically by the API route at `src/app/api/upload-all/route.ts`). The Next.js backend acts as a client to this gRPC service, sending car images for plate detection and receiving the results. This demonstrates a gRPC-based microservice architecture.
