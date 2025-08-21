#!/usr/bin/env python3
import subprocess
import sys
import shutil

script_name = "stride"
script_path = shutil.which(script_name)

if script_path:
    # Launch the script with any additional arguments
    subprocess.run([sys.executable, script_path] + sys.argv[1:])
else:
    print(f"Script '{script_name}' not found in PATH")
    sys.exit(1)
