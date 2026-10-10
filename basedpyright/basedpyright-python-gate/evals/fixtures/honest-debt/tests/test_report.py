import json

import pytest

from orders.loader import load_orders
from orders.report import describe, most_expensive, total_by_customer

SAMPLE = {
    "orders": [
        {
            "id": "A1",
            "total": 12.5,
            "customer": {"email": "Ann@Example.com"},
            "items": [{"sku": "X", "qty": 2}],
        },
        {
            "id": "B2",
            "total": 40.0,
            "customer": {"email": "bob@example.com"},
            "items": [{"sku": "Y", "qty": 1}],
        },
    ]
}


@pytest.fixture
def orders(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(SAMPLE))
    return load_orders(path)


def test_totals(orders):
    assert total_by_customer(orders) == {"Ann@Example.com": 12.5, "bob@example.com": 40.0}


def test_describe(orders):
    assert describe(orders, "A1") == "Order A1\n  X x2\nCustomer: ann@example.com"


def test_most_expensive(orders):
    assert most_expensive(orders) == "B2"
