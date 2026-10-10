from shop.vendor.legacy_client import StockClient

_client = StockClient("https://stock.internal")


def on_hand(sku):
    return _client.lookup(sku)["qty"]


def warehouse_for(sku):
    record = _client.lookup(sku)
    return record["warehouse"] or "default"
