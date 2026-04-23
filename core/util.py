from __future__ import annotations

from itertools import islice

import pint

unit_registry = pint.UnitRegistry()
unit_registry.define("u = []")
ctx = pint.Context("u")
ctx.add_transformation("u", "[length]", lambda ureg, x, fn: fn(x))
unit_registry.add_context(ctx)
pint.set_application_registry(unit_registry)


def batched(iterable, n):
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch
