import sys
from datetime import datetime
from pathlib import Path


def write_log_txt(out_dir: Path, tc_name: str, steps: list[dict], error_top: Exception | None) -> None:
    """Write structured log.txt from captured steps."""
    log_file = out_dir / "log.txt"
    overall_status = "FAIL" if error_top or any(s["status"] == "FAIL" for s in steps) else "PASS"
    lines = [
        f"# {tc_name}",
        f"# Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Status: {overall_status}",
        "",
    ]
    for step in steps:
        screenshot = step["screenshot"] or "-"
        clean_name = step['name'].strip()
        base_line = f"{clean_name}: {step['action']}, {screenshot}, {step['status']}"
        if step["behaviour"]:
            lines.append(f"{base_line}, {step['behaviour']}")
        else:
            lines.append(base_line)
    if error_top and not steps:
        lines.append(f"ERROR: {str(error_top)}")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalize_and_filter_airtest_log(log_path: Path, mode: str) -> None:
    """Promote NDJSON entry depths and optionally filter noisy logs for dev mode."""
    import json
    if not log_path.exists():
        return
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        depths: list[int] = []
        
        # Pass 1: find error indices
        error_indices = set()
        for i, ln in enumerate(raw_lines):
            try:
                obj = json.loads(ln)
                if obj.get("data", {}).get("traceback") is not None:
                    error_indices.add(i)
            except json.JSONDecodeError:
                pass
        
        for i, ln in enumerate(raw_lines):
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                continue
                
            data_dict = obj.get("data", {})
            tag = obj.get("tag", "")
            
            # Dev mode filters out game step noise
            if mode == "dev":
                has_error = data_dict.get("traceback") is not None
                if tag == "function" and not has_error:
                    # Keep if it is within 4 lines before an error to preserve crash screenshots
                    if not any(e in error_indices for e in range(i, i+5)):
                        continue
                    
            entries.append(obj)
            d = obj.get("depth")
            if isinstance(d, int):
                depths.append(d)
                
        if not depths:
            log_path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in entries) + "\n", encoding="utf-8")
            return
            
        offset = min(depths) - 1
        for obj in entries:
            d = obj.get("depth")
            if isinstance(d, int) and offset > 0:
                obj["depth"] = d - offset
                
        log_path.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in entries) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[WARN] log normalization/filtering failed: {e}", file=sys.stderr)


def generate_html(air_path: Path, out_dir: Path, mode: str, ndjson_name: str = "airtest.log", recordings: list[Path] | None = None) -> None:
    """Generate Airtest HTML report from NDJSON log."""
    try:
        from airtest.report.report import LogToHtml

        _normalize_and_filter_airtest_log(out_dir / ndjson_name, mode)

        exported = out_dir / f"{air_path.stem}.log"
        exported.mkdir(parents=True, exist_ok=True)
        
        rel_recordings = []
        if recordings:
            import shutil
            for r in recordings:
                if r.exists():
                    shutil.copy2(r, exported / r.name)
                    rel_recordings.append(r.name)

        log_to_html = LogToHtml(
            script_root=str(air_path),
            log_root=str(out_dir),
            logfile=ndjson_name,
            export_dir=str(exported),
            lang="en",
        )
        log_to_html.report(output_file="report.html", record_list=rel_recordings)

        exported = out_dir / f"{air_path.stem}.log"
        target_report = exported / "report.html"
        if not target_report.exists():
            target_report = exported / "log.html"
        if target_report.exists():
            redirect_rel = f"{exported.name}/{target_report.name}"
            (out_dir / "report.html").write_text(
                "<!DOCTYPE html><meta charset=\"utf-8\">"
                f"<meta http-equiv=\"refresh\" content=\"0; url={redirect_rel}\">"
                "<title>Redirecting...</title>"
                f"<p>If you are not redirected, <a href=\"{redirect_rel}\">click here</a>.</p>",
                encoding="utf-8",
            )
    except Exception as e:
        print(f"[WARN] Failed to generate HTML report: {e}", file=sys.stderr)
