import pytest
from dagster.device.ldplayer_ctl import wait_ready


def test_wait_ready_true_and_stabilizes_when_device_appears():
    """Device healthy on first poll -> returns True after the stabilize sleep."""
    sleeps = []
    assert wait_ready(timeout=60, _poll=lambda: [object()], _sleep=sleeps.append) is True
    assert 10 in sleeps  # STABILIZE wait fired before returning


def test_wait_ready_false_on_timeout():
    """No device ever appears -> returns False once virtual clock passes timeout."""
    t = [0.0]

    def clock():
        return t[0]

    def sleep(s):
        t[0] += s  # advance virtual time so the loop terminates without real waiting

    assert wait_ready(timeout=5, _poll=lambda: [], _sleep=sleep, _clock=clock) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
