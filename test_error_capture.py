import logging
from dagster.error_capture import (
    ErrorCaptureHandler, attach_error_handler, clear_errors, get_errors, had_errors
)

def test_handler_captures_error_level():
    clear_errors()
    logger = logging.getLogger("pixon.test_capture")
    handler = ErrorCaptureHandler()
    logger.addHandler(handler)
    logger.error("boom")
    assert had_errors() is True
    errors = get_errors()
    assert len(errors) == 1
    assert errors[0]["msg"] == "boom"
    logger.removeHandler(handler)

def test_handler_ignores_warning():
    clear_errors()
    logger = logging.getLogger("pixon.test_ignore")
    handler = ErrorCaptureHandler()
    logger.addHandler(handler)
    logger.warning("noise")
    assert had_errors() is False
    assert len(get_errors()) == 0
    logger.removeHandler(handler)

def test_clear_errors_resets():
    clear_errors()
    logger = logging.getLogger("pixon.test_clear")
    handler = ErrorCaptureHandler()
    logger.addHandler(handler)
    logger.error("boom")
    assert had_errors() is True
    clear_errors()
    assert had_errors() is False
    assert len(get_errors()) == 0
    logger.removeHandler(handler)

def test_attach_idempotent():
    clear_errors()
    logger = logging.getLogger("pixon.test_idempotent")
    # clear all handlers first just in case
    logger.handlers.clear()
    
    attach_error_handler("pixon.test_idempotent")
    handlers = [h for h in logger.handlers if isinstance(h, ErrorCaptureHandler)]
    assert len(handlers) == 1
    
    # attach again
    attach_error_handler("pixon.test_idempotent")
    handlers = [h for h in logger.handlers if isinstance(h, ErrorCaptureHandler)]
    assert len(handlers) == 1

def test_capture_includes_metadata():
    clear_errors()
    logger = logging.getLogger("pixon.test_meta")
    handler = ErrorCaptureHandler()
    logger.addHandler(handler)
    logger.error("metadata test")
    
    err = get_errors()[0]
    assert "ts" in err
    assert err["logger"] == "pixon.test_meta"
    assert err["msg"] == "metadata test"
    assert "screenshot" in err
    logger.removeHandler(handler)
