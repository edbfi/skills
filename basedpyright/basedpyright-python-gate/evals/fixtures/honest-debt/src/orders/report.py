"""Summaries over loaded orders."""

from collections import defaultdict

from orders.loader import customer_email, find_order


def total_by_customer(orders):
    totals = defaultdict(float)
    for order in orders:
        totals[customer_email(order)] += order["total"]
    return dict(totals)


def describe(orders, order_id):
    order = find_order(orders, order_id)
    lines = [f"Order {order['id']}"]
    for item in order["items"]:
        lines.append(f"  {item['sku']} x{item['qty']}")
    email = customer_email(order)
    lines.append("Customer: " + email.lower())
    return "\n".join(lines)


def most_expensive(orders):
    best = None
    for order in orders:
        if best is None or order["total"] > best["total"]:
            best = order
    return best["id"]
