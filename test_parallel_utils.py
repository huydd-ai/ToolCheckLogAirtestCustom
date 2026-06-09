from parallel_utils import partition, parse_adb_devices


def test_partition_even():
    assert partition(["a", "b", "c", "d", "e", "f"], 3) == [["a", "b"], ["c", "d"], ["e", "f"]]


def test_partition_uneven_remainder_goes_first():
    assert partition(["a", "b", "c", "d", "e", "f", "g"], 3) == [["a", "b", "c"], ["d", "e"], ["f", "g"]]


def test_partition_fewer_items_than_buckets():
    assert partition(["a", "b"], 3) == [["a"], ["b"], []]


def test_partition_zero_buckets():
    assert partition(["a"], 0) == []


ADB_SAMPLE = (
    "List of devices attached\n"
    "emulator-5554\tdevice\n"
    "RZ8N20ABCDE\tdevice\n"
    "10.0.0.5:5555\toffline\n"
    "FA7890XYZ\tunauthorized\n"
    "\n"
)


def test_parse_returns_only_ready_devices():
    assert parse_adb_devices(ADB_SAMPLE) == ["emulator-5554", "RZ8N20ABCDE"]


def test_parse_empty():
    assert parse_adb_devices("List of devices attached\n\n") == []
