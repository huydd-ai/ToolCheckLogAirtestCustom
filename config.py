from pathlib import Path

def get_paths():
    project_root = Path(__file__).resolve().parent.parent
    return {
        "PROJECT_ROOT": str(project_root),
        "PIXON_DIR": str(project_root / "pixon"),
        "TEST_DIR": str(project_root / "Test")
    }
