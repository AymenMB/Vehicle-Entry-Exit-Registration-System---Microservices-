import os
import sys
import json
import random

def main():
    """
    Test script that accepts an image path and returns a plate detection result.
    """
    # Get the image path from command line arguments
    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Output debugging information
    print(f"Debug: Processing image at: {image_path}", file=sys.stderr)
    
    # If we have an image path, generate a more realistic plate number
    # Otherwise use a default
    if image_path and os.path.exists(image_path):
        # Generate a random plate number that looks like a Tunisian plate
        num1 = random.randint(1000, 9999)
        num2 = random.randint(100, 999)
        plate_number = f"{num1} TN {num2}"
        confidence = random.uniform(0.85, 0.98)
        
        print(f"Debug: Detected plate from: {image_path}", file=sys.stderr)
    else:
        plate_number = "DEBUG-MODEL-123"
        confidence = 0.98
        if image_path:
            print(f"Debug: Image not found: {image_path}", file=sys.stderr)
    
    # Return a mock detection result
    result = {
        "success": True,
        "plateNumber": plate_number,
        "confidence": confidence,
        "error": None
    }
    
    # Print the result as JSON to stdout
    print(json.dumps(result))
    
    # Exit with success code
    return 0

if __name__ == "__main__":
    sys.exit(main())
