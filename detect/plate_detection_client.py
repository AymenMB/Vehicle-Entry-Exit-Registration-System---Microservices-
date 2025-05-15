"""
gRPC client for the plate detection service
"""
import grpc
import sys
import os
import json # Import json for output
import argparse # Import argparse for command-line argument parsing

# Add protos directory to path if necessary (adjust relative path if needed)
# sys.path.append(os.path.join(os.path.dirname(__file__), 'protos')) # Assuming protos is sibling to detect
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Go up one level from detect
from protos import plate_detection_pb2, plate_detection_pb2_grpc

def run_client(image_path):
    """Sends an image path to the gRPC server and returns the detection result."""
    result = {
        "success": False,
        "plateNumber": "",
        "confidence": 0.0,
        "error": ""
    }
    try:
        # Ensure the image file exists
        if not os.path.exists(image_path):
            result["error"] = f"Error: Image file not found at {image_path}"
            return result

        # Read image bytes
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # Establish connection and call the service
        # Increased timeout, e.g., to 30 seconds, especially for the first run or complex images
        channel = grpc.insecure_channel('localhost:50051')
        stub = plate_detection_pb2_grpc.PlateDetectionServiceStub(channel)
        response = stub.DetectPlate(
            plate_detection_pb2.PlateRequest(image=image_bytes, filename=os.path.basename(image_path)),
            timeout=30 # Increased timeout
        )

        # --- Use correct field names from .proto ---
        result["success"] = response.success
        result["plateNumber"] = response.plate_number
        result["confidence"] = response.confidence
        if not response.success and response.error_message:
            result["error"] = response.error_message

    except grpc.RpcError as e:
        # Attempt to provide more specific gRPC error details
        status_code = e.code()
        details = e.details()
        error_msg = f"gRPC error: {status_code.name}"
        if details:
            error_msg += f" ({details})"
        # Check for specific status codes like DEADLINE_EXCEEDED
        if status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
            error_msg += " - The request timed out."
        elif status_code == grpc.StatusCode.UNAVAILABLE:
             error_msg += " - The server might not be running or is unreachable."
        result["error"] = error_msg
    except Exception as e:
        result["error"] = f"Client error: {type(e).__name__}: {e}"

    return result

def main():
    parser = argparse.ArgumentParser(description='Detect license plate from car image')
    parser.add_argument('image_path', help='Path to the car image')
    args = parser.parse_args()
    
    detection_result = run_client(args.image_path) # Use the function

    # Print JSON result only
    print(json.dumps(detection_result, indent=2))

    # Removed human-readable summary from stdout
    # print(f"Success: {detection_result['success']}")
    # print(f"Plate Number: {detection_result['plateNumber']}")
    # print(f"Confidence: {detection_result['confidence']:.2f}")
    # if detection_result['error']:
    #     print(f"Error: {detection_result['error']}") # Access the 'error' key

if __name__ == "__main__":
    main()
