import sys
import subprocess
import os
from shutil import move

def run_script(script_name, args=None):
    print(f" Running {script_name}...")
    command = ["python", script_name]
    if args:
        command += args
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f" {script_name} failed.")
        print(result.stderr)
        sys.exit(1)
    print(f" {script_name} ran successfully.\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python automater.py path/to/file.sh3d output_folder")
        sys.exit(1)

    input_path = sys.argv[1]
    output_folder = sys.argv[2]

    if not os.path.exists(input_path):
        print("File does not exist:", input_path)
        sys.exit(1)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Step 1: Run processing scripts
    run_script("extract_sh3d_xml.py", [input_path])
    run_script("json_generator.py")
    run_script("graph.py")
    # Commented out visualizer to avoid blocking UI
    # run_script("visualizer.py")

    # Step 2: Move expected outputs to the output folder
    for filename in ["walkable_graph_clean.json", "sh3d_elements_with_ids.json"]:
        if os.path.exists(filename):
            move(filename, os.path.join(output_folder, filename))
        else:
            print(f" Missing expected output: {filename}")
            sys.exit(1)

    print(f" All output files moved to {output_folder}")
