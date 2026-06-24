"""Simple HTTP server for the aggregate test report.

Serves static files from REPORT_ROOT and handles DELETE requests.

Usage:
    python report_server.py [--port PORT] [--root REPORT_ROOT]
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from dagster.aggregate_report import regenerate_global_report


def extract_air_path(log_path: Path) -> str | None:
    """Read AIR_PATH= from first line of log.txt. Returns None if absent or unreadable."""
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline().rstrip("\n")
    except OSError:
        return None
    if first_line.startswith("AIR_PATH="):
        return first_line[len("AIR_PATH="):]
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


def _compute_etag(folder_names: list[str]) -> str:
    """Stable 16-char hex ETag from sorted folder name list."""
    return hashlib.md5(",".join(sorted(folder_names)).encode()).hexdigest()[:16]


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

REPORT_ROOT = Path(__file__).parent / "report_run"


class ReportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPORT_ROOT.resolve()), **kwargs)

    def end_headers(self):
        path = self.translate_path(self.path)
        if path.endswith('.html') or path.endswith('.htm'):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def translate_path(self, path):
        # Strip query string for route matching
        clean_path = path.split('?', 1)[0].split('#', 1)[0]
        if clean_path == "/":
            path = path.replace("/", "/report.html", 1)
        return super().translate_path(path)

    def do_POST(self):
        if self.path.startswith("/delete/"):
            folder_name = self.path.removeprefix("/delete/")
            target = REPORT_ROOT / folder_name
            if not target.exists() or not target.is_dir():
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "not found"}).encode())
                return
            try:
                shutil.rmtree(target)
                regenerate_global_report(REPORT_ROOT)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"deleted": folder_name}).encode())
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
        if self.path == "/run":
            self._handle_run()
            return
        self.send_response(405)
        self.end_headers()

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
            import os
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
        self._json(200, {"job_id": job_id})

    def _handle_rerun_terminate(self, job_id: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None:
            self._json(404, {"error": "unknown job"})
            return
        if job["status"] == "running":
            try:
                job["proc"].terminate()
            except OSError:
                pass
            try:
                import subprocess
                import os
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
        self._json(200, {"status": "terminated"})

    def _handle_rerun(self, folder_name: str) -> None:
        target = REPORT_ROOT / folder_name
        if not target.is_dir():
            self._json(404, {"error": "not found"})
            return
        air_path = extract_air_path(target / "log.txt")
        if air_path is None:
            self._json(422, {"error": "no air_path in log"})
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
            import os
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
            from dagster.aggregate_report import scan_runs
            entries = scan_runs(REPORT_ROOT)
            folder_names = [e.folder for e in entries]
            etag = _compute_etag(folder_names)
            client_etag = self.headers.get("If-None-Match", "")
            if client_etag == etag:
                self.send_response(304)
                self.end_headers()
                return
            data = [
                {
                    "stem": e.stem,
                    "when": e.when.isoformat(),
                    "status": e.status,
                    "folder": e.folder,
                    "report_href": e.report_href,
                }
                for e in entries
            ]
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_GET(self):
        # Strip query/fragment before route matching (same as translate_path)
        clean = self.path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/rerun-status/"):
            job_id = clean.removeprefix("/rerun-status/")
            self._handle_rerun_status(job_id)
            return
        if clean == "/api/runs":
            self._handle_api_runs()
            return
        if clean.startswith("/rerun-logs/"):
            job_id = clean.removeprefix("/rerun-logs/")
            self._handle_rerun_logs(job_id)
            return
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

    server = ThreadingHTTPServer(("0.0.0.0", args.port), ReportHandler)
    print(f"[report_server] Serving {REPORT_ROOT} at http://localhost:{args.port}/")
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
