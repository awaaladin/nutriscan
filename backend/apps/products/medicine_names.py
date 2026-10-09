"""Keyword list used to flag submissions/scans that are medicine, not food.

There is no public, searchable barcode database for Nigerian-manufactured
pharmaceuticals (Emzor, Fidson, May & Baker, etc. aren't indexed in any of
the standard barcode-lookup services) and even multinational brands like
Panadol don't surface their Nigeria-market barcodes through search -- so
unlike packaged foods, this can't be seeded from real barcodes. Matching is
done on the product *name* instead, at the point a name is actually known
(a community submission, or an Open Food Facts category/label match).

Brand names below were compiled from pharmacy-market research on Nigeria's
best-selling OTC categories (analgesics, antimalarials, antibiotics,
multivitamins) -- see apps/products/views.py for where this is applied.
"""

GENERIC_MEDICINE_KEYWORDS = (
    "medicine", "medicines", "medication", "drug", "drugs", "pharmaceutical",
    "pharmaceuticals", "tablet", "tablets", "capsule", "capsules",
    "antibiotic", "antibiotics", "analgesic", "analgesics", "antimalarial",
    "antimalarials", "otc-drug", "prescription", "syrup-medicine", "vaccine",
    "antacid", "antipyretic", "antirheumatic",
)

# Real, researched Nigerian OTC/common-drug brand names (paracetamol,
# antimalarials, antibiotics, multivitamins, analgesics). Not exhaustive --
# meant to catch the products people actually buy, not every NAFDAC listing.
NIGERIAN_DRUG_BRAND_KEYWORDS = (
    # Paracetamol / analgesics
    "emzor paracetamol", "emzor", "panadol", "boska", "m&b paracetamol",
    "may & baker paracetamol", "para-", "buscopan", "tramadol", "diclofenac",
    "naproxen", "ibuprofen", "nurofen", "andrews liver salt", "alabukun",
    # Antimalarials
    "lokmal", "coartem", "lonart", "artesunate", "amodiaquine", "metakelfin",
    "nivaquine", "chloroquine", "fansidar", "camosunate",
    # Antibiotics / anti-infectives
    "augmentin", "amoxil", "amoxicillin", "ampiclox", "septrin",
    "ciprotab", "ciprofloxacin", "flagyl", "metronidazole", "gentamycin",
    "loxaclav", "aluclox",
    # Multivitamins / supplements sold as medicine (not food supplements)
    "emvit-c", "multivite", "cestra",
    # Other common Fidson/May & Baker/Emzor lines
    "gascol", "biosulin", "arthemed", "tuxil", "cardovasc", "diamet",
    "artelum",
)

MEDICINE_KEYWORDS = GENERIC_MEDICINE_KEYWORDS + NIGERIAN_DRUG_BRAND_KEYWORDS


def is_known_medicine_name(*texts: str) -> bool:
    haystack = " ".join(t for t in texts if t).lower()
    return any(keyword in haystack for keyword in MEDICINE_KEYWORDS)
