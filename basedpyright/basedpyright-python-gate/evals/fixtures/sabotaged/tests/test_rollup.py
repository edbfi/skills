from metrics.rollup import percentile, rollup


def test_rollup():
    assert rollup([1, 2, 3]) == {"mean": 2, "n": 3}


def test_percentile():
    assert percentile([5, 1, 3], 0.5) == 3
