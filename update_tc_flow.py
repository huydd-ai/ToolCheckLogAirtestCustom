import os
import glob
import re

test_dir = r"d:\AutoRebase\Test\MagicBean"
tc_files = glob.glob(os.path.join(test_dir, "**", "*.py"), recursive=True)

standard_block = """        log_info("Start: tap icon -> confirm board via event_board_character img")
        opened = run_step("open event via icon", magic_bean.open_event_popup)
        assert opened and magic_bean.wait_for_element(magic_bean.event_board, timeout=5), (
            "Result: Expected: event board (character img) visible after tapping icon | "
            "Actual: board not detected"
        )
        log_info("Result: Expected: board confirmed via event_board_character | Actual: confirmed")
        log_info("End: confirm board open")"""

# Patterns to replace
pattern1 = re.compile(r"^[ \t]*assert run_step\([\"']open event popup[\"'], magic_bean\.open_event_popup\), \(\n[ \t]*[\"'].*?[\"']\n[ \t]*\)", re.MULTILINE)
pattern2 = re.compile(r"^[ \t]*if not magic_bean\.open_event_popup\((?:timeout=\d+)?\):\n[ \t]*raise AssertionError\(\n[ \t]*[\"'].*?[\"'][ \t]*\n[ \t]*[\"'].*?[\"']\n[ \t]*\)", re.MULTILINE)
pattern3 = re.compile(r"^[ \t]*if not magic_bean\.open_event_popup\((?:timeout=\d+)?\):\n[ \t]*raise AssertionError\([\"'].*?[\"']\)", re.MULTILINE)

for file in tc_files:
    if "tc01" in file:
        continue
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content
    # Replace pattern 1
    new_content = pattern1.sub(standard_block, new_content)
    # Replace pattern 2
    new_content = pattern2.sub(standard_block, new_content)
    # Replace pattern 3
    new_content = pattern3.sub(standard_block, new_content)
    
    if new_content != content:
        with open(file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(file)}")
