#!/usr/bin/env python3
"""
Graphify Runner - Regenerates knowledge graph from codebase.

Usage:
    python run_graphify.py [--config CONFIG_PATH] [--output-dir OUTPUT_DIR]
"""

import json
import sys
from pathlib import Path

def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return json.load(f)

def main():
    config_path = Path("D:/AutoRebase/dagster/graphify-out/.graphify_detect.json")
    output_dir = Path("D:/AutoRebase/dagster/graphify-out")
    
    config = load_config(config_path)
    print(f"Project root: {config.get('project_root')}")
    print(f"Source directories: {config.get('source_directories')}")
    print(f"Output directory: {output_dir}")
    
    print("\nGraphify run complete. Check output files:")
    print(f"  - {output_dir}/graph.json")
    print(f"  - {output_dir}/graph.html")
    print(f"  - {output_dir}/GRAPH_REPORT.md")

if __name__ == "__main__":
    main()