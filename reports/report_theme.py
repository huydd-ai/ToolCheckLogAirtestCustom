"""Shared dark-theme CSS for the dashboard and per-run report.

Single source of truth so both pages match. Imported (dual-context: runtime
uses ``dagster.reports.report_theme``, run from ``dagster/reports/`` use bare
``report_theme``) and inlined into each generated page's ``<style>``.
"""

# ponytail: one palette here, both pages var() off it. Change colors in one place.
THEME_CSS = """
:root {
  --bg: #0f1115;
  --bg-card: #1a1d24;
  --bg-item: #252a33;
  --text-main: #e2e8f0;
  --text-dim: #94a3b8;
  --border: #334155;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --pass: #10b981;
  --fail: #ef4444;
  --skip: #64748b;
  --r: 8px;
}
* { box-sizing: border-box; }
body {
  font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text-main);
  margin: 0;
}
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }
.t-pass { color: var(--pass); }
.t-fail { color: var(--fail); }
.t-skip { color: var(--skip); }
""".strip()
