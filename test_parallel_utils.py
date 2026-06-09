from parallel_utils import partition


def test_partition_even():
    assert partition(["a", "b", "c", "d", "e", "f"], 3) == [["a", "b"], ["c", "d"], ["e", "f"]]


def test_partition_uneven_remainder_goes_first():
    assert partition(["a", "b", "c", "d", "e", "f", "g"], 3) == [["a", "b", "c"], ["d", "e"], ["f", "g"]]


def test_partition_fewer_items_than_buckets():
    assert partition(["a", "b"], 3) == [["a"], ["b"], []]


def test_partition_zero_buckets():
    assert partition(["a"], 0) == []
