import argparse
import sys
from pathlib import Path

from airtest.core.api import *

parser = argparse.ArgumentParser(description="Run airtest .air projects")
parser.add_argument("target", type=Path, nargs="?", default=Path("."))
parser.add_argument("--device", type=str, default=None)
parser.add_argument("--recording", action=argparse.BooleanOptionalAction, default=True)
args, _ = parser.parse_known_args()

target = args.target.resolve()
if target.suffix == ".air" and target.exists():
    tests = [target]
elif target.is_dir():
    tests = sorted(target.glob("*.air")) or sorted(target.rglob("*.air"))
else:
    tests = []

if not tests:
    sys.exit(f"No .air projects found at {target}")

device_id = "device"
if args.device:
    uri = args.device if args.device.lower().startswith("android://") \
        else f"Android://127.0.0.1:5037/{args.device}"
    connect_device(uri)
    device_id = args.device.rsplit("/", 1)[-1]
else:
    init_device()
    device_id = G.DEVICE.serialno

script_dir = Path(__file__).resolve().parent
scrcpy_path = str(script_dir / "scrcpy-win64" / "scrcpy.exe")
sys.path.insert(0, str(script_dir))

for air_path in tests:
    air_py = air_path / f"{air_path.stem}.py"
    if not air_py.exists():
        continue

    module_name = air_path.stem

    auto_setup(str(air_py))
    G.LOGGER.set_logfile(None)

    recorder = None
    recording_path = Path.cwd() / f"recording_{device_id}_{module_name}.mp4"
    if args.recording:
        from ScrcpyRecorder import ScrcpyRecorder
        recorder = ScrcpyRecorder(output=recording_path, device=device_id, scrcpy_path=scrcpy_path)
        recorder.start()

    sys.path.insert(0, str(air_path))
    try:
        sys.modules.pop(module_name, None)
        mod = __import__(module_name)
        if hasattr(mod, "main"):
            mod.main()
    except Exception as e:
        print(f"[FAILED] {module_name}: {e}")
    finally:
        if recorder:
            try:
                recorder.stop()
            except Exception as e:
                print(f"[WARN] recorder stop: {e}")
        sys.path.remove(str(air_path))

try:
    G.DEVICE.adb.kill_server()
except Exception:
    pass
