"""Product integrity percentage: how likely our data says a product is genuine.

Pure logic with no Django dependencies, like apps.scoring.engine, so it stays
unit-testable. The number blends two things:

1. A prior from verifiable signals about the barcode itself (valid GS1
   checksum, whether an independent database like Open Food Facts knows it).
2. Community real/fake votes, which pull the number toward 100 or 0.

The prior acts like PRIOR_WEIGHT imaginary votes, so a single early vote can't
swing a product from 50% to 0% -- but a handful of independent "fake" reports
will. A valid checksum alone can't prove authenticity (counterfeiters copy real
barcodes), which is why votes exist at all.
"""
from dataclasses import dataclass

PRIOR_WEIGHT = 4
SYNTHETIC_PREFIX = "AI-"

BASE_PRIOR = 40.0
CHECKSUM_VALID_BONUS = 15.0
INDEPENDENT_DB_BONUS = 25.0
INVALID_CHECKSUM_PRIOR = 10.0
SYNTHETIC_BARCODE_PRIOR = 20.0

# Vote totals at which we are willing to call the number reliable.
MEDIUM_CONFIDENCE_VOTES = 3
HIGH_CONFIDENCE_VOTES = 10


@dataclass
class IntegrityResult:
    percent: int
    confidence: str  # "low" | "medium" | "high"
    real_votes: int
    fake_votes: int
    checksum_valid: bool
    in_independent_db: bool


def gtin_checksum_valid(barcode: str) -> bool:
    """GS1 mod-10 check for EAN-8 / UPC-A / EAN-13 / GTIN-14."""
    if not barcode.isdigit() or len(barcode) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in barcode]
    check = digits.pop()
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10 == check


def _prior(barcode: str, checksum_valid: bool, in_independent_db: bool) -> float:
    if barcode.startswith(SYNTHETIC_PREFIX):
        return SYNTHETIC_BARCODE_PRIOR
    if not checksum_valid:
        return INVALID_CHECKSUM_PRIOR
    prior = BASE_PRIOR + CHECKSUM_VALID_BONUS
    if in_independent_db:
        prior += INDEPENDENT_DB_BONUS
    return prior


def compute_integrity(
    barcode: str, in_independent_db: bool, real_votes: int, fake_votes: int
) -> IntegrityResult:
    checksum_valid = gtin_checksum_valid(barcode)
    prior = _prior(barcode, checksum_valid, in_independent_db)
    total = real_votes + fake_votes

    percent = (PRIOR_WEIGHT * prior + 100.0 * real_votes) / (PRIOR_WEIGHT + total)

    if total >= HIGH_CONFIDENCE_VOTES:
        confidence = "high"
    elif total >= MEDIUM_CONFIDENCE_VOTES:
        confidence = "medium"
    else:
        confidence = "low"

    return IntegrityResult(
        percent=round(percent),
        confidence=confidence,
        real_votes=real_votes,
        fake_votes=fake_votes,
        checksum_valid=checksum_valid,
        in_independent_db=in_independent_db,
    )
