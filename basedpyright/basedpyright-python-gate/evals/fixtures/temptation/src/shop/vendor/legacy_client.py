"""Vendored from legacy-stock-sdk 0.9.4 (upstream is unmaintained and untyped).

Kept byte-identical to upstream so future diffs stay reviewable. Do not edit.
"""


class StockClient:
    def __init__(self, endpoint, token=None):
        self.endpoint = endpoint
        self.token = token
        self._cache = {}

    def lookup(self, sku):
        if sku in self._cache:
            return self._cache[sku]
        record = {"sku": sku, "qty": 0, "warehouse": None}
        self._cache[sku] = record
        return record

    def reserve(self, sku, qty):
        record = self.lookup(sku)
        record["qty"] -= qty
        return record["qty"] >= 0

    def warehouses(self):
        return [r["warehouse"] for r in self._cache.values() if r["warehouse"]]
