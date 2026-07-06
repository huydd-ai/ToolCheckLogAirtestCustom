"""Simple HTTP server for the aggregate test report.

Serves static files from REPORT_ROOT and handles POST actions
(delete, delete-date, rerun, rerun-terminate, terminate-all, run).

Usage:
    python report_server.py [--port PORT] [--root REPORT_ROOT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_dagster_dir = Path(__file__).resolve().parent
_project_root = _dagster_dir.parent
sys.path.insert(0, str(_project_root))

PROJECT_ROOT = _project_root
TEST_ROOT = (_project_root / "Test").resolve()

from dagster.reports.aggregate_report import parse_run_folder_name, regenerate_global_report


def extract_air_path(log_path: Path) -> str | None:
    """Read AIR_PATH= from first line of log.txt. Returns None if absent or unreadable."""
    try:
        first_line = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        if first_line.startswith("AIR_PATH="):
            return first_line.removeprefix("AIR_PATH=")
    except (OSError, IndexError):
        pass
    return None


def _find_newest_folder(report_root: Path, stem: str) -> str | None:
    """Return the lexicographically latest folder name matching <stem>_YYYYMMDD_HHMMSS."""
    pattern = re.compile(rf"^{re.escape(stem)}_\d{{8}}_\d{{6}}$")
    candidates = [
        child.name
        for child in report_root.iterdir()
        if child.is_dir() and pattern.match(child.name)
    ]
    return max(candidates) if candidates else None


def _compute_etag(folders_with_mtime: list[tuple[str, float]]) -> str:
    """Stable 16-char hex ETag from sorted folder names and mtimes."""
    s = ",".join(f"{f}:{m}" for f, m in sorted(folders_with_mtime))
    return hashlib.md5(s.encode()).hexdigest()[:16]


_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _find_running_job(suite: str, stem: str) -> dict | None:
    """Return a still-running job for (suite, stem), reaping any whose process
    already exited. Caller must hold _jobs_lock."""
    for job in _jobs.values():
        if job.get("suite") == suite and job["stem"] == stem and job["status"] == "running":
            rc = job["proc"].poll()
            if rc is None:
                return job
            # process exited but never reaped (client poller died) — reap it
            job["exit_code"] = rc
            job["status"] = "done" if rc == 0 else "failed"
            if "log_file" in job and not job["log_file"].closed:
                job["log_file"].close()
    return None


def _any_job_running() -> bool:
    """True if any job is still running, reaping procs that already exited so a
    dead-but-unreaped job (client poller died) doesn't wrongly report running.
    Acquires _jobs_lock itself — caller must NOT hold it."""
    with _jobs_lock:
        for job in _jobs.values():
            if job.get("status") != "running":
                continue
            rc = job["proc"].poll()
            if rc is None:
                return True
            job["exit_code"] = rc
            job["status"] = "done" if rc == 0 else "failed"
            lf = job.get("log_file")
            if lf is not None and not lf.closed:
                lf.close()
    return False


_JOBS_MAX = 100


def _prune_jobs() -> None:
    """Evict oldest finished jobs above _JOBS_MAX, closing their log handle and
    unlinking the .log file. Caller must hold _jobs_lock.
    ponytail: simple count cap; running jobs are never evicted."""
    if len(_jobs) <= _JOBS_MAX:
        return
    finished = sorted(
        (j for j in _jobs.values() if j["status"] != "running"),
        key=lambda j: j["started"],
    )
    for job in finished[: len(_jobs) - _JOBS_MAX]:
        lf = job.get("log_file")
        if lf and not lf.closed:
            lf.close()
        lp = job.get("log_path")
        if lp:
            try:
                lp.unlink()
            except OSError:
                pass
        _jobs.pop(job["job_id"], None)


def _terminate_job(job: dict) -> None:
    """Terminate a running job's process, force-stop the game app, mark the
    job failed and close its log handle. No-op if the job already finished."""
    if job["status"] != "running":
        return
    try:
        job["proc"].terminate()
    except OSError:
        pass
    try:
        try:
            from dotenv import load_dotenv
            # Load .env from dagster/ directory
            load_dotenv(dotenv_path=Path(__file__).parent / ".env")
        except ImportError:
            pass
        pkg = os.environ.get("GAME_PACKAGE", "com.woodpuzzle.pin3d")
        subprocess.run(["adb", "shell", "am", "force-stop", pkg], check=False)
    except Exception:
        pass
    with _jobs_lock:
        if job["status"] != "running":  # reaped as done while we were terminating
            return
        job["status"] = "failed"
        job["exit_code"] = job["proc"].poll()
        lf = job.get("log_file")
        if lf and not lf.closed:
            lf.close()


REPORT_ROOT = Path(__file__).parent / "report_run"


def _safe_under_root(folder_name: str) -> Path | None:
    """Resolve folder_name under REPORT_ROOT, rejecting path traversal.
    Returns the resolved Path or None if it escapes the root."""
    root = REPORT_ROOT.resolve()
    target = (root / folder_name).resolve()
    return target if (target == root or root in target.parents) else None


class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_ROOT.resolve()), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        # Strip query string for route matching
        clean_path = path.split('?', 1)[0].split('#', 1)[0]
        if clean_path == "/":
            return str((Path(__file__).parent / "static" / "index.html").resolve())
        if clean_path.startswith("/static/"):
            rel = clean_path.removeprefix("/static/")
            return str((Path(__file__).parent / "static" / rel).resolve())
        return super().translate_path(path)

    def do_POST(self):
        if self.path.startswith("/delete/"):
            folder_name = self.path.removeprefix("/delete/").split("?", 1)[0]
            target = _safe_under_root(folder_name)
            if target is None or not target.exists() or not target.is_dir():
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "not found"}).encode())
                return
            try:
                # Clear logs and all files inside the folder
                log_files = []
                for item in target.iterdir():
                    if item.is_file() and item.suffix in ('.txt', '.log') or item.name.startswith('log'):
                        log_files.append(item.name)
                shutil.rmtree(target)
                regenerate_global_report(REPORT_ROOT)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"deleted": folder_name, "logs_cleared": log_files}).encode())
            except OSError as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        if self.path.startswith("/delete-date/"):
            date_str = self.path.removeprefix("/delete-date/")
            folder_re = re.compile(r"^.+_(\d{8})_\d{6}$")
            deleted = []
            errors = []
            for child in REPORT_ROOT.iterdir():
                if not child.is_dir():
                    continue
                m = folder_re.match(child.name)
                if not m:
                    continue
                folder_ymd = m.group(1)
                iso_date = f"{folder_ymd[:4]}-{folder_ymd[4:6]}-{folder_ymd[6:]}"
                if iso_date != date_str:
                    continue
                try:
                    shutil.rmtree(child)
                    deleted.append(child.name)
                except OSError as e:
                    errors.append({"folder": child.name, "error": str(e)})
            if deleted:
                regenerate_global_report(REPORT_ROOT)
            body = json.dumps({"deleted": deleted, "errors": errors})
            status = 200 if deleted else 404
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
            return
        if self.path.startswith("/rerun/"):
            folder_name = self.path.removeprefix("/rerun/")
            self._handle_rerun(folder_name)
            return
        if self.path.startswith("/rerun-terminate/"):
            job_id = self.path.removeprefix("/rerun-terminate/")
            self._handle_rerun_terminate(job_id)
            return
        if self.path == "/terminate-all":
            self._handle_terminate_all()
            return
        if self.path == "/run":
            self._handle_run()
            return
        if self.path == "/emulator/start":
            self._handle_emulator_start()
            return
        if self.path == "/emulator/stop":
            self._handle_emulator_stop()
            return
        self.send_response(405)
        self.end_headers()

    def _handle_emulator_start(self) -> None:
        from dagster.device import ldplayer_ctl
        from dagster.device.device_manager import device_manager
        # Idempotent: already-booted device -> ready now, no launch, no stabilize wait.
        try:
            if device_manager.get_healthy_devices():
                self._json(200, {"status": "ready"})
                return
        except Exception:
            pass  # health probe hiccup -> fall through to launch
        try:
            ldplayer_ctl.launch()
        except FileNotFoundError:
            self._json(500, {"error": "ldconsole not found"})
            return
        if ldplayer_ctl.wait_ready(60):
            self._json(200, {"status": "ready"})
        else:
            self._json(504, {"error": "emulator did not become ready"})

    def _handle_emulator_stop(self) -> None:
        from dagster.device import ldplayer_ctl
        # Guard: another run still needs the emulator -> keep it (single instance).
        if _any_job_running():
            self._json(200, {"status": "kept", "reason": "job running"})
            return
        ldplayer_ctl.quit()
        self._json(200, {"status": "stopped"})

    def _handle_run(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = json.loads(self.rfile.read(length) or b"{}")
            air_path = payload.get("air_path", "")
        except (ValueError, OSError):
            self._json(400, {"error": "bad request body"})
            return
        if not air_path:
            self._json(400, {"error": "air_path required"})
            return
        p = (PROJECT_ROOT / air_path).resolve()
        if not (p.exists() and p.suffix == ".air" and TEST_ROOT in p.parents):
            self._json(400, {"error": "path must be an existing .air under Test/"})
            return
        suite = p.parent.name or "unknown"
        stem = p.stem
        with _jobs_lock:
            if _find_running_job(suite, stem) is not None:
                self._json(409, {"error": "already running"})
                return
            job_id = str(uuid.uuid4())
            log_path = REPORT_ROOT / f"{job_id}.log"
            log_file = log_path.open("w", encoding="utf-8")
            dagster_run = Path(__file__).parent / "dagster_run.py"
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", str(dagster_run), str(p)],
                    stdout=log_file, stderr=subprocess.STDOUT, env=env,
                )
            except FileNotFoundError:
                log_file.close()
                self._json(500, {"error": "dagster_run.py not found"})
                return
            _jobs[job_id] = {
                "job_id": job_id, "suite": suite, "stem": stem,
                "air_path": str(p), "proc": proc, "status": "running",
                "new_folder": None, "exit_code": None, "started": time.time(),
                "log_file": log_file, "log_path": log_path,
            }
            _prune_jobs()
        self._json(200, {"job_id": job_id})

    def _handle_rerun_terminate(self, job_id: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            self._json(404, {"error": "unknown job"})
            return
        _terminate_job(job)
        self._json(200, {"status": "terminated"})

    def _handle_terminate_all(self) -> None:
        with _jobs_lock:
            running = [j for j in _jobs.values() if j["status"] == "running"]
        for job in running:
            _terminate_job(job)
        self._json(200, {"terminated": [j["job_id"] for j in running]})

    def _handle_rerun(self, folder_name: str) -> None:
        target = _safe_under_root(folder_name)
        if target is None or not target.is_dir():
            self._json(404, {"error": "not found"})
            return
        air_path = extract_air_path(target / "log.txt")
        if air_path is None:
            self._json(422, {"error": "no air_path in log"})
            return
        # Validate before handing to subprocess: must be an existing .air under Test/
        ap = (PROJECT_ROOT / air_path).resolve()
        if not (ap.exists() and ap.suffix == ".air" and TEST_ROOT in ap.parents):
            self._json(422, {"error": "air_path not a valid .air under Test/"})
            return
        m = re.match(r"^(.+)_\d{8}_\d{6}$", folder_name)
        if not m:
            self._json(400, {"error": "invalid folder name"})
            return
        stem = m.group(1)
        suite = Path(air_path).parent.name or "unknown"
        with _jobs_lock:
            if _find_running_job(suite, stem) is not None:
                self._json(409, {"error": "already running"})
                return
            job_id = str(uuid.uuid4())
            log_path = REPORT_ROOT / f"{job_id}.log"
            # Keep file open for the lifetime of the process
            log_file = log_path.open("w", encoding="utf-8")
            
            dagster_run = Path(__file__).parent / "dagster_run.py"
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-u", str(dagster_run), air_path],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=env
                )
            except FileNotFoundError:
                log_file.close()
                self._json(500, {"error": "dagster_run.py not found"})
                return
            
            _jobs[job_id] = {
                "job_id": job_id,
                "stem": stem,
                "suite": suite,
                "air_path": air_path,
                "proc": proc,
                "status": "running",
                "new_folder": None,
                "exit_code": None,
                "started": time.time(),
                "log_file": log_file,
                "log_path": log_path,
            }
            _prune_jobs()
        self._json(200, {"job_id": job_id})

    def _handle_rerun_status(self, job_id: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            self._json(404, {"error": "unknown job"})
            return
        if job["status"] == "running":
            rc = job["proc"].poll()
            if rc is not None:
                with _jobs_lock:
                    job = _jobs.get(job_id, job)
                    job["exit_code"] = rc
                    job["status"] = "done" if rc == 0 else "failed"
                    job["new_folder"] = _find_newest_folder(REPORT_ROOT, job["stem"])
                    if "log_file" in job and not job["log_file"].closed:
                        job["log_file"].close()
        self._json(200, {
            "status": job["status"],
            "new_folder": job.get("new_folder"),
            "exit_code": job.get("exit_code"),
        })

    def _handle_api_runs(self) -> None:
        try:
            from dagster.reports.report_data import scan_runs
            runs = scan_runs(REPORT_ROOT)

            folder_info = []
            for r in runs:
                log_path = REPORT_ROOT / r.folder / "log.txt"
                mtime = log_path.stat().st_mtime if log_path.exists() else 0.0
                folder_info.append((r.folder, mtime))
                
            etag = _compute_etag(folder_info)
            if self.headers.get("If-None-Match", "") == etag:
                self.send_response(304)
                self.end_headers()
                return
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", etag)
            self.end_headers()
            payload = json.dumps([r.to_dict() for r in runs]).encode("utf-8")
            self.wfile.write(payload)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _handle_api_metrics(self) -> None:
        try:
            from dagster.reports.report_data import scan_runs, compute_metrics
            runs = scan_runs(REPORT_ROOT)
            metrics = compute_metrics(runs)
            self._json(200, metrics)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _handle_api_catalog(self) -> None:
        try:
            from dagster.reports.report_data import scan_catalog
            catalog = scan_catalog(TEST_ROOT)
            self._json(200, catalog)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_GET(self):
        # Strip query/fragment before route matching (same as translate_path)
        clean = self.path.split("?", 1)[0].split("#", 1)[0]
        
        if clean == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if clean.startswith("/rerun-status/"):
            job_id = clean.removeprefix("/rerun-status/")
            self._handle_rerun_status(job_id)
            return
        if clean == "/api/runs":
            self._handle_api_runs()
            return
        if clean == "/api/metrics":
            self._handle_api_metrics()
            return
        if clean == "/api/catalog":
            self._handle_api_catalog()
            return
        if clean.startswith("/rerun-logs/"):
            job_id = clean.removeprefix("/rerun-logs/")
            self._handle_rerun_logs(job_id)
            return
        # Rebuild on page load so newly-added Test/ cases show in the catalog
        # without a restart or write event. ponytail: cheap globs, fine per-load.
        if clean == "/report.html":
            try:
                regenerate_global_report(REPORT_ROOT)
            except Exception as e:
                sys.stderr.write(f"[report_server] regen on GET failed: {e}\n")
        super().do_GET()

    def _handle_rerun_logs(self, job_id: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            self._json(404, {"error": "unknown job"})
            return
        
        from urllib.parse import parse_qs
        query = parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
        offset = int(query.get("offset", ["0"])[0])
        
        log_path = job.get("log_path")
        if not log_path or not log_path.exists():
            self._json(200, {"text": "", "offset": offset})
            return
            
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                text = f.read()
                new_offset = f.tell()
            self._json(200, {"text": text, "offset": new_offset})
        except OSError as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[report_server] {args[0]}\n")

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main():
    global REPORT_ROOT
    parser = argparse.ArgumentParser(description="Dagster test report server")
    parser.add_argument("--port", type=int, default=7070)
    parser.add_argument("--root", type=str, default=str(REPORT_ROOT))
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Bind address. Default loopback-only; use 0.0.0.0 to expose on LAN.")
    args = parser.parse_args()

    REPORT_ROOT = Path(args.root).resolve()
    if not REPORT_ROOT.exists():
        REPORT_ROOT.mkdir(parents=True)
        print(f"[report_server] Created root: {REPORT_ROOT}")

    # Ensure the global report is generated before serving
    try:
        regenerate_global_report(REPORT_ROOT)
    except Exception as e:
        print(f"[report_server] Failed to regenerate report: {e}")

    server = ThreadingHTTPServer((args.host, args.port), ReportHandler)
    print(f"[report_server] Serving {REPORT_ROOT} at http://localhost:{args.port}/ (bind {args.host})")
    print(f"[report_server] DELETE endpoint: http://localhost:{args.port}/delete/<folder>")
    print(f"[report_server] DELETE-DATE endpoint: http://localhost:{args.port}/delete-date/<YYYY-MM-DD>")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[report_server] Shutting down")
        with _jobs_lock:
            for job in _jobs.values():
                if job["status"] == "running":
                    try:
                        job["proc"].terminate()
                    except OSError:
                        pass
        server.server_close()


if __name__ == "__main__":
    main()
