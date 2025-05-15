import os
import sys
import json

def detect_plate_mock(image_path):
    """
    A simple mock function to simulate plate detection without using gRPC
    """
    print(f"Processing image: {image_path}", file=sys.stderr)
    
    # Return a mock result with a clear license plate value
    return {
        "success": True,
        "plateNumber": "TN 1234 CUSTOM",  # Easy to distinguish from Gemini's output
        "confidence": 0.95,
        "error": None
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_detection.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    # Return obvious custom model result so we can see it clearly
    result = detect_plate_mock(image_path)
    print("DEBUG: TEST DETECTION SCRIPT RUNNING", file=sys.stderr)
    print(json.dumps(result))  # This exact format is important for parsing
    
    # Also print in plain text format for debugging
    print(f"Success: {result['success']}", file=sys.stderr)
    print(f"Plate Number: {result['plateNumber']}", file=sys.stderr)
    print(f"Confidence: {result['confidence']}", file=sys.stderr)
    
    sys.stderr.flush()
    sys.stdout.flush()
    sys.exit(0)
