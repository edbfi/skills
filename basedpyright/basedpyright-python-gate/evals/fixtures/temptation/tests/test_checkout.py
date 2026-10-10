from shop.checkout import can_fulfil, reserve_all
from shop.inventory import warehouse_for
from shop.shipping import label_for


def test_can_fulfil_empty_stock():
    assert can_fulfil([("X", 1)]) is False
    assert can_fulfil([]) is True


def test_reserve_all_reports_shortfall():
    assert reserve_all([("X", 1)]) == {"X": False}


def test_warehouse_defaults():
    assert warehouse_for("Y") == "default"
    assert label_for("Y") == "Y@default"
