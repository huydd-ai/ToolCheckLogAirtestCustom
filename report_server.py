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

from aggregate_report import regenerate_global_report


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
        self.send_response(405)
        self.end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[report_server] {args[0]}\n")

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Dagster test report server")
    parser.add_argument("--port", type=int, default=7070)
    parser.add_argument("--root", type=str, default=str(REPORT_ROOT))
    args = parser.parse_args()

    REPORT_ROOT_PATH = Path(args.root).resolve()
    if not REPORT_ROOT_PATH.exists():
        REPORT_ROOT_PATH.mkdir(parents=True)
        print(f"[report_server] Created root: {REPORT_ROOT_PATH}")

    server = ThreadingHTTPServer(("0.0.0.0", args.port), ReportHandler)
    print(f"[report_server] Serving {REPORT_ROOT_PATH} at http://localhost:{args.port}")
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
