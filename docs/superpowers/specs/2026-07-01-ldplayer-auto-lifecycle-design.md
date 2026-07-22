# LDPlayer Auto Open/Close on Dashboard Run Buttons — Design Spec

**Date:** 2026-07-01
**Status:** Approved, pending implementation plan

## Goal

When a user taps a **run** button on the dashboard (`▶ Run`, `↺ Rerun`, `▶ Run All`),
auto-launch the LDPlayer emulator, wait until it is booted + ADB-healthy + stable,
run the test(s), then auto-close the emulator when the run reaches any terminal state
(success, FAIL, crash, or manual terminate).

Today nothing launches or closes an emulator anywhere in `dagster/` or `pixon/` — the rig
assumes a device is already booted and ADB-reachable. This design adds that lifecycle,
scoped to the dashboard run buttons only.

## Decisions (locked)

| Dimension | Choice |
|-----------|--------|
| Emulator | LDPlayer (`ldconsole.exe`) |
| Instances | Single instance, index 0 |
| Trigger scope | Dashboard run buttons only (single `▶ Run`, `↺ Rerun`, and `▶ Run All`). Not CLI `dagster_run.py`. |
| Run-All behavior | Open **once** before the batch, close **once** after — emulator stays up across the whole batch, no per-test open/close mid-batch. |
| Close triggers | Any terminal state: success, FAIL, crash, manual terminate. |
| Orchestration | Client-orchestrated (`app.js`) calling two new thin server endpoints. |
| Stabilize wait | After boot is detected, `sleep(10)` before returning so the test inserts into a settled emulator. |
| Path/index | Hardcoded `C:\LDPlayer\LDPlayer9\ldconsole.exe`, index `0` (module consts in `ldplayer_ctl.py`). |

## Why client-orchestrated, not baked into `/run` / `/rerun`

`▶ Run All` (`runSuite` in `app.js`) loops the **same** `/run` call that the single `▶ Run`
button uses — the server cannot distinguish "single click" from "batch iteration" at the
`/run` endpoint. Putting open/close inside `/run`/`/rerun` would reopen/reclose the emulator
between every test in a batch, violating the run-all decision. So the open/close steps are
**separate endpoints the client sequences**: `runSuite` calls start once / stop once around
its loop; single-test buttons call start / (run) / stop around one test.

## Architecture

### Component 1 — `ldplayer_ctl.py` (new, `dagster/`, beside `device_manager.py`)

Thin subprocess wrapper. Stdlib only (`subprocess`, `time`, `logging`). No new dependency.

Module consts:
```python
LDCONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"
INDEX = 0
```

Functions:
- `launch()` — `subprocess.run([LDCONSOLE, "launch", "--index", str(INDEX)], check=False)`.
- `quit()` — `subprocess.run([LDCONSOLE, "quit", "--index", str(INDEX)], check=False)`;
  wrapped in try/except. On any failure **log it** (server logger / stdout) — never silent,
  never surfaced to the UI. (Architect fix #3.)
- `wait_ready(timeout=60) -> bool` — poll `device_manager.get_healthy_devices()` every 2 s.
  On first non-empty result: `time.sleep(10)` (stabilize) then return `True`.
  On timeout: return `False` (caller maps to HTTP 504). Reuses the existing boot/health
  probing in `device_manager` — no new health logic.

`if __name__ == "__main__":` self-check — `launch()` → `wait_ready()` → `quit()` against a
real LDPlayer, printing each step's result. (ponytail: non-trivial branch needs one runnable
check; real emulator boot can't be unit-tested, so this is the check.)

### Component 2 — two new POST routes in `report_server.py`

Registered in `do_POST` alongside the existing `/run`, `/rerun/`, `/rerun-terminate/` routes.
Both return JSON via the existing `_json(code, dict)` helper.

- **`POST /emulator/start`** — idempotent:
  1. If `device_manager.get_healthy_devices()` is already non-empty → `200 {"status":"ready"}`
     immediately. No `launch()`, **no 10 s wait** (already booted + stable from an earlier run).
  2. Else `ldplayer_ctl.launch()` → `ldplayer_ctl.wait_ready(60)`:
     - `True` → `200 {"status":"ready"}`
     - `False` → `504 {"error":"emulator did not become ready"}`
  3. `ldconsole.exe` missing (`FileNotFoundError`) → `500 {"error":"ldconsole not found"}`.

- **`POST /emulator/stop`** — guarded, best-effort:
  1. **Guard (architect fix #1):** under `_jobs_lock`, scan `_jobs.values()` for any job with
     `status == "running"`. If one exists, **skip quit** and return
     `200 {"status":"kept","reason":"job running"}` — another run still needs the emulator.
     (Single instance + per-button stop would otherwise let job A's finish yank the emulator
     out from under still-running job B in another tab / concurrent run.)
  2. Else `ldplayer_ctl.quit()` → `200 {"status":"stopped"}`. Errors are logged, not surfaced.

### Component 3 — `app.js` client sequencing

Two helpers:
- `async startEmulator()` — `POST /emulator/start`; return `true` on 200, `false` otherwise.
- `async stopEmulator()` — `POST /emulator/stop`; fire-and-forget (ignore result/errors).

Wire into the three run paths:

- **`rerunTest(folder)`** — `if (!await startEmulator()) { jobs[folder]={status:'emulator failed to start'}; return; }`
  then the existing `/rerun/` + `pollJob` flow unchanged.
- **`runCatalogTest(suite, stem, standalone=true)`** — same start-gate when `standalone`;
  existing `/run` flow unchanged; passes `standalone` through to `pollJob`.
- **`pollJob(jobId, key, standalone=true)`** — add the `standalone` param (threaded from the
  caller). Its single terminal branch (already the one chokepoint for done/failed) calls
  `await stopEmulator()` before resolving **when `standalone`**. This covers success, FAIL, and
  terminate uniformly (terminate also drives the job to a terminal status, so `pollJob` resolves
  and stop fires). `runSuite`'s iterations call `runCatalogTest(..., false)` → `pollJob(..., false)`
  → no per-test stop; the batch's single `finally` stop handles close.
- **`runSuite(suite)`** — `if (!await startEmulator()) { alert('Emulator failed to start'); return; }`
  before the loop; loop calls `runCatalogTest(suite, t, false)` (per-iteration start/stop
  skipped); `stopEmulator()` in a `finally` after the loop so a mid-batch error still closes it.

Passing `standalone` (default `true`) threads the batch flag so per-test stop is suppressed
inside `runSuite` but the belt-and-suspenders server-side guard (Component 2, step 1) still
protects the cross-tab case.

## Data flow

```
Single Run / Rerun:
  tap → POST /emulator/start ──(launch + wait_ready: boot-detect + 10s stabilize)──> 200
      → existing POST /run|/rerun/  (unchanged)
      → existing pollJob (unchanged) ── terminal (done/failed/terminated) ──
      → POST /emulator/stop ──(guard: other job running? → keep)──> quit → UI update

Run All:
  tap → POST /emulator/start (once)
      → loop: runCatalogTest(..., standalone=false)  [no per-test start/stop]
      → finally: POST /emulator/stop (once, guarded)
```

## Error handling

- **Start timeout / missing exe** → 504 / 500; client never calls `/run`; single-test job row
  shows `'emulator failed to start'`; `runSuite` alerts and aborts the batch (no test attempted).
- **Stop failure** (`ldconsole` error) → logged server-side, `200` still returned; UI unaffected.
  Emulator may be left open, but the failure is in the log, not silent (architect fix #3).
- **Concurrent stop while another job runs** → guard keeps the emulator up (architect fix #1).
- **Double-launch race** (two near-simultaneous `/emulator/start` both see "not healthy" and
  both `launch()`) → accepted risk. `ldconsole launch` on an already-launching index is a
  no-op/refocus in practice. ponytail: fix when observed, not preemptively.

## Testing

- `ldplayer_ctl.py` — `__main__` self-check (launch → wait_ready → quit) against real LDPlayer.
- API — spin `report_server` against a temp `REPORT_ROOT`; assert `/emulator/start` returns
  `200 {"status":"ready"}` when a healthy device is already present (mock/stub
  `device_manager.get_healthy_devices`), and `/emulator/stop` returns `{"status":"kept"}` when a
  fake `_jobs` entry has `status=="running"` vs `{"status":"stopped"}` when none do. These two
  are the non-trivial branches worth a headless test; the real launch/quit path is covered by
  the `__main__` check.
- SPA — manual smoke (no JS test framework — matches existing dashboard testing, ponytail).

## Phasing (→ implementation plan)

1. `ldplayer_ctl.py`: `launch` / `quit` (logged) / `wait_ready` (boot-detect + 10 s stabilize)
   + `__main__` self-check.
2. `report_server.py`: `POST /emulator/start` (idempotent, health-first) + `POST /emulator/stop`
   (running-job guard + logged best-effort quit); register in `do_POST`; headless branch tests.
3. `app.js`: `startEmulator` / `stopEmulator` helpers; gate `rerunTest` + single `runCatalogTest`;
   `stopEmulator` in `pollJob` terminal branch (standalone only); `runSuite` open-once /
   close-once with `standalone=false` loop calls.

## Out of scope (YAGNI)

- Multi-instance / serial↔index mapping (single instance only).
- CLI path — `python dagster_run.py ...` does not open/close the emulator; dashboard only.
- Stuck / frozen-instance repair (restart-on-hang) — separate concern.
- Configurable path/index via `.env` — hardcoded consts; promote to `.env` if a second rig needs it.
- Double-launch mutex — accepted race, see Error handling.
