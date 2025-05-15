"""Generate Python gRPC code from cin_extraction.proto file"""
import os
import subprocess
import sys

def generate_cin_grpc_code():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proto_file_name = "cin_extraction.proto"
    proto_path = os.path.join(script_dir, "protos", proto_file_name)
    output_dir = os.path.join(script_dir, "protos")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate gRPC Python code
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={os.path.dirname(proto_path)}", # Should be the directory containing the 'cin_extraction.proto'
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        proto_path
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        print(f"Error generating gRPC code for CIN extraction: {result.stderr}")
        # Attempt to create __init__.py if it doesn't exist, as this can sometimes be an issue
        # with protoc not finding the proto file if the package structure isn't perfect.
        # However, the primary issue is usually proto_path or the file itself.
        init_py_path = os.path.join(output_dir, "__init__.py")
        if not os.path.exists(init_py_path):
            print(f"Attempting to create missing {init_py_path}")
            try:
                with open(init_py_path, 'w') as f:
                    f.write("# Required for protobuf imports\n")
                print(f"Successfully created {init_py_path}")
                # Retry generation
                print("Retrying gRPC code generation...")
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    print(f"Retry Error generating gRPC code for CIN extraction: {result.stderr}")
                    sys.exit(1)
            except Exception as e:
                print(f"Could not create {init_py_path}: {e}")
                sys.exit(1)
        else:
            sys.exit(1)

    print("Successfully generated gRPC Python code for CIN extraction.")
    
    # Fix imports in generated _pb2_grpc.py code
    # The generated gRPC stub file will be named based on the proto file
    pb2_grpc_file_name = proto_file_name.replace(".proto", "_pb2_grpc.py")
    pb2_grpc_file_path = os.path.join(output_dir, pb2_grpc_file_name)

    pb2_file_name_for_import = proto_file_name.replace(".proto", "_pb2")
    
    if os.path.exists(pb2_grpc_file_path):
        with open(pb2_grpc_file_path, 'r') as f:
            content = f.read()
        
        # Fix the import statement
        # Example: import cin_extraction_pb2 as cin__extraction__pb2
        original_import = f"import {pb2_file_name_for_import} as {pb2_file_name_for_import.replace('_', '__')}"
        corrected_import = f"from . import {pb2_file_name_for_import} as {pb2_file_name_for_import.replace('_', '__')}"
        
        if original_import in content:
            fixed_content = content.replace(original_import, corrected_import)
            with open(pb2_grpc_file_path, 'w') as f:
                f.write(fixed_content)
            print(f"Fixed imports in {pb2_grpc_file_path}")
        else:
            print(f"Warning: Could not find the expected import line '{original_import}' in {pb2_grpc_file_path}. Manual check might be needed.")
    else:
        print(f"Error: Generated file {pb2_grpc_file_path} not found. Cannot fix imports.")

if __name__ == "__main__":
    generate_cin_grpc_code()
