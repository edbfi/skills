from shop.vendor.legacy_client import StockClient

_client = StockClient("https://stock.internal")


def active_warehouses():
    names = _client.warehouses()
    return sorted(set(names))


def label_for(sku):
    record = _client.lookup(sku)
    return f"{record['sku']}@{record['warehouse'] or 'default'}"
