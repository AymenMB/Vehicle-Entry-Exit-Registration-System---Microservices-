"""Generate Python gRPC code from proto file"""
import os
import subprocess
import sys

def generate_grpc_code():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proto_path = os.path.join(script_dir, "protos", "plate_detection.proto")
    output_dir = os.path.join(script_dir, "protos")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate gRPC Python code
    # Use sys.executable to ensure the correct python interpreter is used
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc", # Use sys.executable
        f"--proto_path={os.path.dirname(proto_path)}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        proto_path
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error generating gRPC code: {result.stderr}")
        sys.exit(1)
    
    print("Successfully generated gRPC Python code")
    
    # Fix imports in generated code
    pb2_file = os.path.join(output_dir, "plate_detection_pb2_grpc.py")
    with open(pb2_file, 'r') as f:
        content = f.read()
    
    # Fix the import statement
    fixed_content = content.replace(
        "import plate_detection_pb2 as plate__detection__pb2",
        "from . import plate_detection_pb2 as plate__detection__pb2"
    )
    
    with open(pb2_file, 'w') as f:
        f.write(fixed_content)
    
    print("Fixed imports in generated code")

if __name__ == "__main__":
    generate_grpc_code()
