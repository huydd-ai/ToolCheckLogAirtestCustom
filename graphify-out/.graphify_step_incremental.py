import sys, json
from graphify.detect import detect_incremental, save_manifest
from pathlib import Path

# Detect incremental changes - the manifest tracks files from D:\AutoRebase\dagster
result = detect_incremental(Path('D:\AutoRebase\dagster'))
print(json.dumps(result, indent=2))
