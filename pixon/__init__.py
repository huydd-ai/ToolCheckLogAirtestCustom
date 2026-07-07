import logging
from pathlib import Path



from airtest.core.api import G

airtest_logger = logging.getLogger("airtest")
airtest_logger.setLevel(logging.ERROR)
for h in airtest_logger.handlers:
    h.setLevel(logging.ERROR)
for name in list(logging.root.manager.loggerDict):
    if name.startswith("airtest"):
        logging.getLogger(name).setLevel(logging.ERROR)

import os

_report_all = os.getenv("REPORT_ALL_STEPS", "true").lower() in ("true", "1", "yes")

if G.LOGGER:
    _orig_log = G.LOGGER.log

    def _error_only_log(tag, data, depth=None, timestamp=None):
        if not _report_all and tag == "function" and data and not data.get("traceback"):
            return
        _orig_log(tag, data, depth, timestamp)

    G.LOGGER.log = _error_only_log

import airtest.core.api as _api

if hasattr(_api.touch, "__wrapped__"):
    _api.touch = _api.touch.__wrapped__

if hasattr(_api.sleep, "__wrapped__"):
    _api.sleep = _api.sleep.__wrapped__

