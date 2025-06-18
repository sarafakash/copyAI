import subprocess

def run_script(script_name):
    print(f"🔄 Running {script_name}...")
    result = subprocess.run(["python", script_name], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f" {script_name} ran successfully.\n")
        print(result.stdout)
    else:
        print(f" Error running {script_name}:\n")
        print(result.stderr)

if __name__ == "__main__":
    scripts_to_run = [
        "extract_sh3d_xml.py",
        "json_generator.py",
        # "nodes.py",         # generates walkable_graph.json
        "graph.py",         # maybe generates static matplotlib visual?
        "visualizer.py"     # creates walkable_graph.html
    ]

    for script in scripts_to_run:
        run_script(script)
