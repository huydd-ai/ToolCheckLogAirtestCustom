import pytest
import dagster.report_server as rs


class _FakeProc:
    def __init__(self, rc):
        self._rc = rc
        self.terminated = False

    def poll(self):
        return self._rc

    def terminate(self):
        self.terminated = True
        self._rc = -15


def test_any_job_running_true_when_running_job_present():
    rs._jobs.clear()
    rs._jobs["j1"] = {"stem": "t", "suite": "s", "status": "running", "proc": _FakeProc(None)}
    try:
        assert rs._any_job_running() is True
    finally:
        rs._jobs.clear()


def test_any_job_running_reaps_exited_job_and_returns_false():
    """A job marked running whose process already exited must be reaped, not counted —
    otherwise a dead-but-unreaped job would wrongly keep the emulator alive."""
    rs._jobs.clear()
    rs._jobs["j1"] = {"stem": "t", "suite": "s", "status": "running", "proc": _FakeProc(0)}
    try:
        assert rs._any_job_running() is False
        assert rs._jobs["j1"]["status"] == "done"
    finally:
        rs._jobs.clear()


def test_terminate_job_kills_running_job(monkeypatch):
    monkeypatch.setattr(rs.subprocess, "run", lambda *a, **k: None)  # skip real adb
    rs._jobs.clear()
    proc = _FakeProc(None)
    job = {"job_id": "j1", "stem": "t", "suite": "s", "status": "running", "proc": proc}
    rs._jobs["j1"] = job
    try:
        rs._terminate_job(job)
        assert proc.terminated is True
        assert job["status"] == "failed"
        assert job["exit_code"] == -15
    finally:
        rs._jobs.clear()


def test_terminate_job_noop_on_finished_job(monkeypatch):
    monkeypatch.setattr(rs.subprocess, "run", lambda *a, **k: None)
    proc = _FakeProc(0)
    job = {"job_id": "j1", "stem": "t", "suite": "s", "status": "done", "proc": proc}
    rs._terminate_job(job)
    assert proc.terminated is False
    assert job["status"] == "done"


def test_second_bind_same_port_fails():
    """Two servers must not silently share one port (Windows SO_REUSEADDR quirk)."""
    s1 = rs.ReportServer(("127.0.0.1", 0), rs.ReportHandler)
    port = s1.server_address[1]
    try:
        with pytest.raises(OSError):
            s2 = rs.ReportServer(("127.0.0.1", port), rs.ReportHandler)
            s2.server_close()
    finally:
        s1.server_close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
