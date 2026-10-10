# pyright: basic
"""Daily rollups."""

from statistics import mean


def rollup(samples):
    return {"mean": mean(samples), "n": len(samples)}  # type: ignore


def percentile(samples, p):
    ordered = sorted(samples)  # pyright: ignore
    index = int(len(ordered) * p)
    return ordered[min(index, len(ordered) - 1)]  # pyright: ignore[reportUnknownVariableType]
