@echo off
echo Clearing old Dagster test runs...
python -c "import shutil, os; r = 'report_run'; shutil.rmtree(r) if os.path.exists(r) else None; os.makedirs(r, exist_ok=True)"
echo Done! Old benchmark data has been cleared.
pause
