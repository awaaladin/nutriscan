"""Barcode matching that tolerates the different ways one product's code is written.

The same GTIN turns up as EAN-13 "0012345678905", UPC-A "012345678905" or
GTIN-14 "00012345678905" depending on the scanner and the pack, so an exact
string match can miss a product we already hold. Lookups therefore match every
equivalent zero-padded form; stored values are left exactly as given.
"""
from typing import List

# Retail GTIN lengths: EAN-8, UPC-A, EAN-13, GTIN-14.
_GTIN_LENGTHS = (8, 12, 13, 14)


def barcode_variants(raw: str) -> List[str]:
    """`raw` first, then every equivalent zero-padded/unpadded form."""
    raw = (raw or "").strip()
    if not raw.isdigit():
        return [raw] if raw else []
    core = raw.lstrip("0") or "0"
    variants = [raw]
    for length in _GTIN_LENGTHS:
        if len(core) <= length:
            padded = core.zfill(length)
            if padded not in variants:
                variants.append(padded)
    return variants


def find_product_by_barcode(raw: str):
    """The product for `raw` under any equivalent form, preferring an exact match."""
    from .models import Product

    variants = barcode_variants(raw)
    if not variants:
        return None
    matches = {p.barcode: p for p in Product.objects.filter(barcode__in=variants)}
    for variant in variants:
        if variant in matches:
            return matches[variant]
    return None
