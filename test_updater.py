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
