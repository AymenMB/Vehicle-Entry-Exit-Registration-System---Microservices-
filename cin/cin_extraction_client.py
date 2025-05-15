"""
CIN Extraction gRPC Client
"""
import grpc
import os
import sys
import json
import argparse

# Add protos directory to sys.path to allow importing generated modules
# This assumes the client is in the 'cin' directory and 'protos' is a subdirectory
PROTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'protos')
if PROTOS_DIR not in sys.path:
    sys.path.append(PROTOS_DIR)

# Now import the generated stubs
try:
    from protos import cin_extraction_pb2
    from protos import cin_extraction_pb2_grpc
except ImportError as e:
    print(f"Error importing protobuf modules from {PROTOS_DIR}: {e}")
    print("Ensure that generate_cin_grpc.py has been run successfully.")
    sys.exit(1)

def run_cin_extraction_client(image_path: str, server_address: str = 'localhost:50052'):
    """Sends a CIN image to the gRPC server and returns the extraction result."""
    result = {
        "success": False,
        "id_number": "",
        "name": "",
        "lastname": "",
        "confidence_id": 0.0,
        "confidence_name": 0.0,
        "confidence_lastname": 0.0,
        "error": ""
    }

    if not os.path.exists(image_path):
        result["error"] = f"Error: Image file not found at {image_path}"
        return result

    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        channel = grpc.insecure_channel(server_address)
        stub = cin_extraction_pb2_grpc.CinExtractionServiceStub(channel)
        
        request_data = cin_extraction_pb2.CinRequest(
            image_data=image_bytes,
            filename=os.path.basename(image_path)
        )
        
        # Increased timeout for potentially complex OCR tasks
        response = stub.ExtractCinData(request_data, timeout=60) 

        result["success"] = response.success
        result["id_number"] = response.id_number
        result["name"] = response.name
        result["lastname"] = response.lastname
        result["confidence_id"] = response.confidence_id
        result["confidence_name"] = response.confidence_name
        result["confidence_lastname"] = response.confidence_lastname
        if not response.success and response.error_message:
            result["error"] = response.error_message

    except grpc.RpcError as e:
        status_code = e.code()
        details = e.details()
        error_msg = f"gRPC error: {status_code.name if hasattr(status_code, 'name') else status_code}"
        if details:
            error_msg += f" ({details})"
        if status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
            error_msg += " - The request timed out."
        elif status_code == grpc.StatusCode.UNAVAILABLE:
            error_msg += f" - The server at {server_address} might not be running or is unreachable."
        result["error"] = error_msg
    except FileNotFoundError:
        result["error"] = f"Error: Image file not found at {image_path}. This check should be redundant due to the initial check."
    except Exception as e:
        result["error"] = f"Client-side error: {type(e).__name__}: {e}"

    return result

def main():
    parser = argparse.ArgumentParser(description='Extract information from a CIN image via gRPC.')
    parser.add_argument('image_path', type=str, help='Path to the CIN image file')
    parser.add_argument('--server', type=str, default='localhost:50052', help='Address of the gRPC server (e.g., localhost:50052)')
    args = parser.parse_args()

    try:
        extraction_result = run_cin_extraction_client(args.image_path, args.server)
    except Exception as e:
        extraction_result = {
            "success": False,
            "error": f"Client-side error: {str(e)}"
        }

    # Ensure stdout is configured for UTF-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    print(json.dumps(extraction_result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
