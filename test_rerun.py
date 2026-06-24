"""Tests for async rerun pipeline."""
from pathlib import Path
from reporting import write_log_txt


def test_write_log_txt_prepends_air_path(tmp_path):
    air_path = tmp_path / "tc01_login.air"
    write_log_txt(tmp_path, "tc01_login", [], None, air_path=air_path)
    first_line = (tmp_path / "log.txt").read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"AIR_PATH={air_path.resolve()}"


def test_write_log_txt_no_air_path_unchanged(tmp_path):
    write_log_txt(tmp_path, "tc01_login", [], None)
    first_line = (tmp_path / "log.txt").read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("# tc01_login")


# ── helpers in report_server ──────────────────────────────────────────────────

def test_extract_air_path_found(tmp_path):
    from report_server import extract_air_path
    log = tmp_path / "log.txt"
    log.write_text("AIR_PATH=/path/to/tc01.air\n# tc01\n", encoding="utf-8")
    assert extract_air_path(log) == "/path/to/tc01.air"


def test_extract_air_path_missing_header(tmp_path):
    from report_server import extract_air_path
    log = tmp_path / "log.txt"
    log.write_text("# tc01\n# Status: PASS\n", encoding="utf-8")
    assert extract_air_path(log) is None


def test_extract_air_path_no_file(tmp_path):
    from report_server import extract_air_path
    assert extract_air_path(tmp_path / "missing.txt") is None


def test_find_newest_folder(tmp_path):
    from report_server import _find_newest_folder
    (tmp_path / "tc01_login_20260619_100000").mkdir()
    (tmp_path / "tc01_login_20260619_110000").mkdir()
    (tmp_path / "tc02_other_20260619_100000").mkdir()
    result = _find_newest_folder(tmp_path, "tc01_login")
    assert result == "tc01_login_20260619_110000"


def test_find_newest_folder_none(tmp_path):
    from report_server import _find_newest_folder
    assert _find_newest_folder(tmp_path, "tc01_login") is None


def test_compute_etag_stable():
    from report_server import _compute_etag
    a = _compute_etag(["tc01_20260619_100000", "tc02_20260619_110000"])
    b = _compute_etag(["tc02_20260619_110000", "tc01_20260619_100000"])
    assert a == b  # order-independent
    assert len(a) == 16


# ── /rerun endpoint ───────────────────────────────────────────────────────────
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import report_server


def _make_test_server(tmp_root: Path, port: int):
    """Spin up report_server pointing at tmp_root, return (server, thread)."""
    report_server.REPORT_ROOT = tmp_root
    report_server._jobs.clear()
    server = ThreadingHTTPServer(("127.0.0.1", port), report_server.ReportHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)  # let server bind
    return server, t


def _post(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_rerun_folder_not_found(tmp_path):
    server, _ = _make_test_server(tmp_path, 17071)
    try:
        status, body = _post("http://127.0.0.1:17071/rerun/nonexistent_20260619_100000")
        assert status == 404
        assert "not found" in body["error"]
    finally:
        server.shutdown()


def test_rerun_no_air_path_in_log(tmp_path):
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    (folder / "log.txt").write_text("# tc01_login\n# Status: PASS\n", encoding="utf-8")
    server, _ = _make_test_server(tmp_path, 17072)
    try:
        status, body = _post("http://127.0.0.1:17072/rerun/tc01_login_20260619_100000")
        assert status == 422
        assert "no air_path" in body["error"]
    finally:
        server.shutdown()


def test_rerun_returns_job_id(tmp_path):
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    # Write a valid log with AIR_PATH pointing to a harmless script
    dummy_air = tmp_path / "tc01_login.air"
    dummy_air.mkdir()
    (dummy_air / "tc01_login.py").write_text("def main(): pass\n", encoding="utf-8")
    (folder / "log.txt").write_text(
        f"AIR_PATH={dummy_air}\n# tc01_login\n# Status: PASS\n", encoding="utf-8"
    )
    server, _ = _make_test_server(tmp_path, 17073)
    try:
        status, body = _post("http://127.0.0.1:17073/rerun/tc01_login_20260619_100000")
        assert status == 200
        assert "job_id" in body
        assert len(body["job_id"]) == 36  # UUID format
    finally:
        with report_server._jobs_lock:
            for job in report_server._jobs.values():
                try:
                    job["proc"].terminate()
                except Exception:
                    pass
        server.shutdown()


def test_rerun_concurrent_guard(tmp_path):
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    dummy_air = tmp_path / "tc01_login.air"
    dummy_air.mkdir()
    (dummy_air / "tc01_login.py").write_text("import time\ndef main(): time.sleep(30)\n", encoding="utf-8")
    (folder / "log.txt").write_text(
        f"AIR_PATH={dummy_air}\n# tc01_login\n# Status: PASS\n", encoding="utf-8"
    )
    server, _ = _make_test_server(tmp_path, 17074)
    try:
        status1, body1 = _post("http://127.0.0.1:17074/rerun/tc01_login_20260619_100000")
        assert status1 == 200
        status2, body2 = _post("http://127.0.0.1:17074/rerun/tc01_login_20260619_100000")
        assert status2 == 409
        assert "already running" in body2["error"]
    finally:
        with report_server._jobs_lock:
            for job in report_server._jobs.values():
                try:
                    job["proc"].terminate()
                except Exception:
                    pass
        server.shutdown()


def test_rerun_reaps_stale_running_job(tmp_path):
    # A prior job whose process already exited but was never reaped (client poller
    # died on page reload) must NOT block a new rerun with a permanent 409.
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    dummy_air = tmp_path / "tc01_login.air"
    dummy_air.mkdir()
    (dummy_air / "tc01_login.py").write_text("def main(): pass\n", encoding="utf-8")
    (folder / "log.txt").write_text(
        f"AIR_PATH={dummy_air}\n# tc01_login\n# Status: PASS\n", encoding="utf-8"
    )
    server, _ = _make_test_server(tmp_path, 17078)
    try:
        import subprocess
        import sys
        stale_proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
        stale_proc.wait()  # exited, but status left as "running"
        report_server._jobs["stale-0000"] = {
            "job_id": "stale-0000",
            "stem": "tc01_login",
            "air_path": str(dummy_air),
            "proc": stale_proc,
            "status": "running",
            "new_folder": None,
            "exit_code": None,
            "started": time.time(),
            "log_file": open(tmp_path / "stale.log", "w", encoding="utf-8"),
            "log_path": tmp_path / "stale.log",
        }
        status, body = _post("http://127.0.0.1:17078/rerun/tc01_login_20260619_100000")
        assert status == 200, body
        assert "job_id" in body
        assert report_server._jobs["stale-0000"]["status"] in ("done", "failed")
    finally:
        with report_server._jobs_lock:
            for job in report_server._jobs.values():
                try:
                    job["proc"].terminate()
                except Exception:
                    pass
        server.shutdown()


# ── /rerun-status endpoint ────────────────────────────────────────────────────

def _get(url: str, headers: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_rerun_status_unknown_job(tmp_path):
    server, _ = _make_test_server(tmp_path, 17075)
    try:
        status, body = _get("http://127.0.0.1:17075/rerun-status/no-such-id")
        assert status == 404
        assert b"unknown job" in body
    finally:
        server.shutdown()


def test_rerun_status_running_then_done(tmp_path):
    # Inject a fake finished job AFTER _make_test_server clears _jobs
    server, _ = _make_test_server(tmp_path, 17076)
    try:
        import subprocess
        fake_proc = subprocess.Popen(
            [__import__("sys").executable, "-c", "import sys; sys.exit(0)"]
        )
        fake_proc.wait()  # already finished with rc=0
        job_id = "test-job-0000"
        report_server._jobs[job_id] = {
            "job_id": job_id,
            "stem": "tc99_fake",
            "air_path": "/fake/tc99.air",
            "proc": fake_proc,
            "status": "running",  # not yet resolved by server
            "new_folder": None,
            "exit_code": None,
            "started": time.time(),
        }
        status, body = _get(f"http://127.0.0.1:17076/rerun-status/{job_id}")
        data = json.loads(body)
        assert status == 200
        assert data["status"] in ("done", "failed")
        assert data["exit_code"] == 0
    finally:
        server.shutdown()


# ── /api/runs endpoint ────────────────────────────────────────────────────────

def test_api_runs_returns_json(tmp_path):
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    (folder / "log.txt").write_text(
        "AIR_PATH=/tc01.air\n# tc01_login\n# Status: PASS\n", encoding="utf-8"
    )
    server, _ = _make_test_server(tmp_path, 17077)
    try:
        status, body = _get("http://127.0.0.1:17077/api/runs")
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)
        assert data[0]["stem"] == "tc01_login"
        assert data[0]["status"] == "PASS"
    finally:
        server.shutdown()


def test_api_runs_etag_304(tmp_path):
    folder = tmp_path / "tc01_login_20260619_100000"
    folder.mkdir()
    (folder / "log.txt").write_text(
        "AIR_PATH=/tc01.air\n# tc01_login\n# Status: PASS\n", encoding="utf-8"
    )
    server, _ = _make_test_server(tmp_path, 17078)
    try:
        status1, body1 = _get("http://127.0.0.1:17078/api/runs")
        assert status1 == 200
        # parse ETag from response headers — we need urlopen for headers
        req = urllib.request.Request("http://127.0.0.1:17078/api/runs")
        with urllib.request.urlopen(req) as r:
            etag = r.headers.get("ETag", "")
        assert etag, "ETag header should be present"
        status2, _ = _get("http://127.0.0.1:17078/api/runs", headers={"If-None-Match": etag})
        assert status2 == 304
    finally:
        server.shutdown()


# ── dashboard HTML ────────────────────────────────────────────────────────────

from aggregate_report import render_html, group_by_date, group_by_suite_then_date, RunEntry
from datetime import datetime


def _make_entry(stem="tc01_login", status="PASS"):
    return RunEntry(
        stem=stem,
        when=datetime(2026, 6, 19, 10, 0, 0),
        status=status,
        folder=f"{stem}_20260619_100000",
        report_href=f"{stem}_20260619_100000/report.html",
    )


def test_dashboard_has_rerun_button():
    html = render_html(group_by_suite_then_date([_make_entry()]))
    assert 'class="rerun-btn"' in html
    assert 'data-folder="tc01_login_20260619_100000"' in html


def test_dashboard_has_rerun_status_span():
    html = render_html(group_by_suite_then_date([_make_entry()]))
    assert 'class="rerun-status"' in html


def test_dashboard_has_rerun_js_functions():
    html = render_html(group_by_suite_then_date([_make_entry()]))
    assert "rerunTest" in html
    assert "pollRerunStatus" in html
    assert "refreshRunList" in html
    assert "clearInterval" in html
