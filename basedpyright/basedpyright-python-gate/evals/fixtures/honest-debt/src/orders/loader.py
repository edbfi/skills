"""Load orders from a JSON export."""

import json
from pathlib import Path


def load_orders(path):
    data = json.loads(Path(path).read_text())
    return data["orders"]


def find_order(orders, order_id):
    for order in orders:
        if order["id"] == order_id:
            return order
    return None


def customer_email(order):
    customer = order.get("customer")
    if customer:
        return customer.get("email")
