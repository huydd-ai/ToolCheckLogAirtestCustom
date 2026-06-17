# Stop-on-Error: Promote Logged Errors to Test Failure

**Date:** 2026-06-17
**Branch:** feat/update-system
**Status:** Design — pending implementation plan

## Problem

A test can complete with `Status: PASS` in `log.txt` and a green banner in `report_summary.html` even when the console clearly printed `[ERROR] …` lines during the run. The report is not honest about failures observers can see in the terminal.

Two confirmed swallow paths in `pixon/common/wrappers.py` allow this:

1. **`wrapper.log_warning(msg)`** (`wrappers.py:448`) prints to the console at WARNING level, then only raises `StepError` when no exception is already active. Inside an `except` block, the warning is logged and execution continues.
2. **`wrapper.log_error(msg)`** (`wrappers.py:422`) prints at ERROR level and raises `StepError(RuntimeError)`. Callers that catch `RuntimeError` (e.g. `pixon/common/autoplay_watchdog.py:72`) swallow the raise and call `log_warning` to keep retrying. If the retry loop eventually succeeds, the test reports PASS even though `[ERROR]` lines were printed.

Constraint from product side: no test-file edits (~70 files). Fix must live on the runner + hook side. Raw `raise AssertionError(...)` lines inside a test's `try/except Exception` block already propagate correctly via `wrapper.log_error`'s re-raise — they are not in scope for this fix.

## Goal

Any `logging.ERROR` (or higher) record emitted under the `pixon` logger during a test run promotes the test's final status to `FAIL`, even if the exception was caught downstream and the test continued. The failure is reflected in `log.txt` (`Status: FAIL`), `report_summary.html` (red banner + visible synthetic step row), and the global aggregated report.

Non-goals:
- Modifying any file under `Test/` or `pixon/`.
- Changing watchdog retry semantics in-place (errors will still propagate and watchdog still retries; only the report status changes).
- Catching WARNING-level records — watchdog retry chatter is left untouched.

## Architecture

New module `dagster/error_capture.py`:

```python
class ErrorCaptureHandler(logging.Handler):
    # level = logging.ERROR

def attach_error_handler(logger_name: str = "pixon") -> None: ...
def clear_errors() -> None: ...
def get_errors() -> list[dict]: ...
def had_errors() -> bool: ...
```

Module-global state:

- `_errors: list[dict]` — each entry: `{"ts": float, "logger": str, "msg": str, "screenshot": str | None}`.
- Captures `_logger.error(...)` and `_logger.critical(...)` calls under the `pixon` logger (and its descendants).
- `attach_error_handler` is idempotent: skips installation if an `ErrorCaptureHandler` is already attached to the target logger.
- `screenshot` is resolved inside `emit` by reusing the screenshot scan already in `dagster.step_capture._latest_screenshot` (the helper is moved to or re-exported from a shared module so both `step_capture` and `error_capture` can call it without duplication).
- Process-local. Multi-device parallelism is process-based (`parallel_utils.partition` + child `python dagster_run.py --device …`), so no cross-process synchronization is required.

## Integration

### `dagster/dagster_run.py`

After `patch_run_step()` (currently `dagster_run.py:40`):

```python
from dagster.error_capture import attach_error_handler
attach_error_handler()
```

### `dagster/runner.py` (`run_single_test`)

- Before `clear_steps()` (line 41): call `clear_errors()`.
- In the `finally` block, after the existing step audit (`runner.py:75`) and before `generate_html`:

```python
errors = get_errors()
if errors and status == "PASS":
    status = "FAIL"

# Promote first logged error as the report-level error_top when no
# natural exception was caught — gives summary report a failure detail.
if errors and error_top is None:
    error_top = RuntimeError(errors[0]["msg"])

# Synthesize FAIL steps for logged errors not already linked to a
# captured run_step.  Dedup: skip when `behaviour` of any existing
# step matches `msg` and the timestamp is within ±2s of the captured
# step.
for err in errors:
    if _matches_existing_step(steps, err):
        continue
    steps.append({
        "name": f"[ERROR] {err['logger']}",
        "action": "logged_error",
        "status": "FAIL",
        "screenshot": err.get("screenshot"),
        "behaviour": err["msg"],
        "duration": 0,
    })
```

`_matches_existing_step` is a small helper local to the runner module (or `error_capture.py`).

### `dagster/reporting.py`

No changes required.

- `write_log_txt` already derives `overall_status` from `error_top` plus any step with `status == "FAIL"`.
- `generate_summary_report` already renders synthetic step rows from the `steps` list and an `error_top` panel.

## Data Flow (per test)

1. Runner calls `clear_steps()` and `clear_errors()`.
2. Test code calls `run_step(...)`, `log_error(...)`, `log_warning(...)`, etc.
3. Any `_logger.error` / `_logger.critical` under the `pixon` logger fires `ErrorCaptureHandler.emit` → record appended to `_errors` with the latest screenshot path.
4. `_orig_run_step` raises → step capture appends a FAIL `_steps` entry.
5. `mod.main()` returns or raises.
6. Runner enters `finally`:
   - Reads `_steps` and `_errors`.
   - Promotes `status` to `FAIL` if `_errors` is non-empty and current `status == "PASS"`.
   - Sets `error_top = RuntimeError(_errors[0]['msg'])` only when no natural exception was caught.
   - Appends a synthetic FAIL step per error not already represented in `_steps`.
7. `generate_html`, `generate_summary_report`, `write_log_txt` run as today and pick up the augmented state.

## Edge Cases

- **Dedup against natural failures.** When `wrapper.log_error` was called inside a `run_step` action and the resulting `StepError` propagated to the step capture's `except`, both a step (status `FAIL`, `behaviour = msg`) and a log record are captured. The synthetic step would be redundant. Dedup rule: skip the synthetic step when any existing step in `_steps` already has `behaviour == err["msg"]`. Match is by exact string equality, no timestamp window (the existing step dict carries only `duration`, not start/end timestamps, so a time-based match would require extending the step schema — out of scope here).
- **Multiple ERRORs in one test.** All are captured; each becomes its own synthetic step. `error_top` is the first error (chronological).
- **Errors during `teardown_app`.** Handler stays attached through the `finally` block. ERROR-level entries from teardown count as failures. WARNING-level ones (`test_flow.py:106 teardown stop_app failed`) are below threshold and do not flip status.
- **Errors before `attach_error_handler` runs.** Initial pixon module-level imports happen earlier. Anything they log is missed. Acceptable — tests do not run yet.
- **Parallel runs.** Each child process owns its own `_errors` list. ✓
- **Handler reinstall.** Idempotency check prevents duplicate records when `attach_error_handler` is called more than once in the same process.
- **Non-pixon errors.** `airtest`, `paddleocr`, and root-logger entries are ignored. If future scope expands, additional `attach_error_handler("airtest")` calls add coverage.
- **Performance.** Handler appends one dict per ERROR record. No I/O. Negligible.

## Testing

New `dagster/test_error_capture.py`:

- `test_handler_captures_error_level` — `_logger.error("boom")` produces one entry; `had_errors()` is True.
- `test_handler_ignores_warning` — `_logger.warning("noise")` produces no entry.
- `test_clear_errors_resets` — emit, clear, assert empty.
- `test_attach_idempotent` — calling `attach_error_handler` twice leaves a single handler installed.
- `test_capture_includes_metadata` — entry contains `ts`, `logger`, `msg` keys.

Extensions in `dagster/test_reporting.py` (or a new `dagster/test_runner_integration.py`):

- `test_runner_promotes_pass_to_fail_on_logged_error` — stub `mod.main()` that calls `pixon._logger.error("…")` and returns normally. After `run_single_test`, `log.txt` line 3 reads `# Status: FAIL`.
- `test_synthetic_step_appended_for_logged_error` — same setup; assert `_steps` contains a `[ERROR] pixon` entry with status `FAIL` and matching `behaviour`.
- `test_dedup_skips_synthetic_when_step_already_captured` — a `run_step` whose action calls `log_error` and lets the raise propagate; assert no synthetic duplicate is appended.

Manual smoke test:

1. Delete or rename a template image used by `autoplay_watchdog` (e.g. a `Booster` template).
2. Run any tc that exercises the watchdog.
3. Confirm: console shows `[ERROR] wrappers.py:428 - …`, `log.txt` line 3 reads `# Status: FAIL`, `report_summary.html` banner is red and contains a `[ERROR] pixon` step row with the original message in the Error column.

## Out of Scope

- Editing the ~70 test files under `Test/` to remove their `try/except Exception` wrappers.
- Changing `wrapper.log_warning`'s "swallow when an exception is active" behavior — watchdog retries continue to work.
- Catching WARNING-level entries. (Future option if needed.)
- Aggregating across tests (existing `aggregate_report.regenerate_global_report` reads each test's `Status:` from `log.txt`, which already picks up the corrected status — no change needed).

## Files Touched

- `dagster/error_capture.py` (new)
- `dagster/runner.py` (modify `run_single_test`)
- `dagster/dagster_run.py` (call `attach_error_handler` after `patch_run_step`)
- `dagster/test_error_capture.py` (new)
- `dagster/test_reporting.py` or new `dagster/test_runner_integration.py` (extend)
