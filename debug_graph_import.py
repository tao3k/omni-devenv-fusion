import sys
import os
from pathlib import Path

# Add project root to python path (assuming we run from root)
sys.path.append(os.getcwd())

# Add scripts dir
scripts_dir = Path("assets/skills/knowledge/scripts")
sys.path.append(str(scripts_dir))

print(f"Importing graph from {scripts_dir}...")
try:
    import graph

    print("Success! Graph module imported.")
    print(f"Attributes: {[a for a in dir(graph) if not a.startswith('_')]}")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback

    traceback.print_exc()
