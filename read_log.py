import os
import glob

def print_latest_log():
    # Find all test_times.txt or error logs
    base_dir = r"d:\AutoRebase\Test"
    logs = glob.glob(os.path.join(base_dir, "**", "test_times.txt"), recursive=True)
    logs += glob.glob(os.path.join(base_dir, "**", "*.txt"), recursive=True)
    
    if not logs:
        print("No logs found.")
        return

    # Sort by modification time
    logs.sort(key=os.path.getmtime, reverse=True)
    
    latest_log = logs[0]
    print(f"Latest log file: {latest_log}")
    print("-" * 50)
    with open(latest_log, "r", encoding="utf-8") as f:
        print(f.read())
        
print_latest_log()
