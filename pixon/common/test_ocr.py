"""Offline self-check for find_all_text_with_conf. Run: python pixon/common/test_ocr.py"""
import numpy as np
import pixon.common.ocr as ocr


class _FakeOcr:
    """Mimics PaddleOCR().ocr() return shape: [[ [box, (text, conf)], ... ]]."""
    def __init__(self):
        self.last_cls = None

    def ocr(self, img, cls=True):
        self.last_cls = cls
        return [[
            [None, ("Win 500", 0.95)],
            [None, ("9 other winners", 0.88)],
            [None, ("noise", 0.30)],
        ]]


def test_with_conf_filters_and_keeps_score():
    fake = _FakeOcr()
    ocr._ocr = fake                # bypass PaddleOCR init
    ocr._ocr_import_error = None
    img = np.zeros((50, 100, 3), dtype=np.uint8)

    lines = ocr.find_all_text_with_conf(img, min_conf=0.4)
    assert [l.text for l in lines] == ["Win 500", "9 other winners"]   # 0.30 dropped
    assert lines[0].conf == 0.95
    assert isinstance(lines[0], ocr.OcrLine)

    # angle classifier is not loaded (use_angle_cls=False) — must not be requested per call
    assert fake.last_cls is False, f"expected cls=False, got cls={fake.last_cls}"

    # find_all_text stays list[str], same filtering
    assert ocr.find_all_text(img) == ["Win 500", "9 other winners"]
    print("test_ocr: all checks passed")


if __name__ == "__main__":
    test_with_conf_filters_and_keeps_score()
