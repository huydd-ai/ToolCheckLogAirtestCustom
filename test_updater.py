"""Unit tests for dagster.updater. All git interaction is mocked."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import updater


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    """Build a successful CompletedProcess result for mock fakes."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


def test_check_and_update_skips_when_parallel_child(monkeypatch, repo_root):
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=True)
    assert calls == []


def test_check_and_update_skips_when_env_opt_out(monkeypatch, repo_root):
    monkeypatch.setenv("DAGSTER_NO_UPDATE", "1")
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=False)
    assert calls == []


def test_check_and_update_skips_when_marker_file_present(monkeypatch, repo_root):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    (repo_root / ".no-update").write_text("")
    calls: list = []
    monkeypatch.setattr(
        updater.subprocess, "run", lambda *a, **k: (calls.append(a), _ok())[1]
    )
    updater.check_and_update(repo_root, is_parallel_child=False)
    assert calls == []


def test_check_and_update_skips_on_detached_head(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return _ok(stdout="HEAD\n")  # detached HEAD sentinel

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert len(calls) == 1
    assert calls[0][:3] == ["git", "rev-parse", "--abbrev-ref"]
    assert "detached" in capsys.readouterr().err.lower()


def test_check_and_update_warns_when_git_missing(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(*a, **k):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "rev-parse failed" in capsys.readouterr().err
def test_check_and_update_warns_on_fetch_timeout(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            raise subprocess.TimeoutExpired(cmd=args, timeout=15)
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "fetch failed" in capsys.readouterr().err


def test_check_and_update_warns_on_fetch_nonzero_exit(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            raise subprocess.CalledProcessError(returncode=128, cmd=args, stderr="auth failed")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "fetch failed" in capsys.readouterr().err


def test_check_and_update_noop_when_already_up_to_date(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="0\n")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    op_names = [c[1] for c in calls]
    assert op_names == ["rev-parse", "fetch", "rev-list"]
    assert "already up to date" in capsys.readouterr().err


def test_check_and_update_pulls_when_behind(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)
    calls: list = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="3\n")
        if args[1] == "merge":
            return _ok()
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    op_names = [c[1] for c in calls]
    assert op_names == ["rev-parse", "fetch", "rev-list", "merge"]
    # Verify the merge call shape exactly
    merge_call = calls[-1]
    assert merge_call == ["git", "merge", "--ff-only", f"origin/main"]
    assert "pulled 3 commits on main" in capsys.readouterr().err


def test_check_and_update_warns_on_pull_failure(monkeypatch, repo_root, capsys):
    monkeypatch.delenv("DAGSTER_NO_UPDATE", raising=False)

    def fake_run(args, **kwargs):
        if args[1] == "rev-parse":
            return _ok(stdout="main\n")
        if args[1] == "fetch":
            return _ok()
        if args[1] == "rev-list":
            return _ok(stdout="2\n")
        if args[1] == "merge":
            raise subprocess.CalledProcessError(returncode=1, cmd=args, stderr="non-fast-forward")
        raise AssertionError(f"unexpected call: {args}")

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.check_and_update(repo_root, is_parallel_child=False)

    assert "pull failed" in capsys.readouterr().err
