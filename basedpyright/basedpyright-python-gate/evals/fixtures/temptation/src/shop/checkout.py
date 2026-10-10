from shop.inventory import on_hand
from shop.vendor.legacy_client import StockClient

_client = StockClient("https://stock.internal")


def can_fulfil(lines):
    return all(on_hand(sku) >= qty for sku, qty in lines)


def reserve_all(lines):
    results = {}
    for sku, qty in lines:
        results[sku] = _client.reserve(sku, qty)
    return results
