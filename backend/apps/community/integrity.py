"""Product trust assessment: evidence tiers, not a made-up percentage.

Pure logic with no Django dependencies, like apps.scoring.engine, so it stays
unit-testable. Nothing here can prove a *specific unit* is genuine -- fakers
copy real barcodes and even real NAFDAC numbers -- so the output is a tier
plus the plain-language reasons behind it, and community reports can always
override a registry match.

Tiers, highest priority first:
  reported_fake  credible weighted reports say fake and clearly outweigh "real"
  disputed       substantial weighted reports on both sides
  verified       NAFDAC number confirmed by an admin against the Greenbook, or
                 the manufacturer's barcode confirmed, with no credible fake reports
  suspicious     barcode isn't a valid retail code (or is app-generated) and
                 nothing verifies the product
  unverified     everything else -- no registry match, little or no evidence
"""
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

SYNTHETIC_PREFIX = "AI-"

FAKE_THRESHOLD = 3.0       # weighted fake reports needed to call it reported_fake
DISPUTE_MIN_WEIGHT = 1.5   # each side needs this much weight to count as disputed

MEDIUM_CONFIDENCE_VOTES = 3
HIGH_CONFIDENCE_VOTES = 10

HEADLINES = {
    "verified": "Registered product",
    "unverified": "Not verified",
    "suspicious": "Suspicious barcode",
    "disputed": "Disputed by users",
    "reported_fake": "Reported as fake",
}


@dataclass
class IntegrityResult:
    tier: str
    headline: str
    reasons: List[str]
    confidence: str  # "low" | "medium" | "high" -- by number of reports
    real_votes: int
    fake_votes: int
    real_weight: float
    fake_weight: float
    checksum_valid: bool
    nafdac_verified: bool
    manufacturer_verified: bool


def gtin_checksum_valid(barcode: str) -> bool:
    """GS1 mod-10 check for EAN-8 / UPC-A / EAN-13 / GTIN-14."""
    if not barcode.isdigit() or len(barcode) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in barcode]
    check = digits.pop()
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10 == check


def compute_integrity(
    barcode: str,
    in_independent_db: bool,
    nafdac_verified: bool,
    manufacturer_verified: bool,
    reports: Iterable[Tuple[str, float]],
) -> IntegrityResult:
    """`reports` is (verdict, weight) per visible report; see
    apps.community.services.report_weight for how weights are earned."""
    real_votes = fake_votes = 0
    real_weight = fake_weight = 0.0
    for verdict, weight in reports:
        if verdict == "fake":
            fake_votes += 1
            fake_weight += weight
        else:
            real_votes += 1
            real_weight += weight

    checksum_valid = gtin_checksum_valid(barcode)
    synthetic = barcode.startswith(SYNTHETIC_PREFIX)
    registry_verified = nafdac_verified or manufacturer_verified

    reasons: List[str] = []
    if nafdac_verified:
        reasons.append("Its NAFDAC registration number was checked against the NAFDAC Greenbook.")
    if manufacturer_verified:
        reasons.append("The manufacturer's barcode has been confirmed.")
    if in_independent_db and not registry_verified:
        reasons.append("The barcode is listed in Open Food Facts, but that doesn't prove a pack is genuine.")
    if synthetic:
        reasons.append("This product was identified from a photo and has no readable barcode.")
    elif not checksum_valid:
        reasons.append("The barcode number is not a valid retail barcode.")
    if fake_votes:
        reasons.append(f"{fake_votes} user report(s) say it's fake.")
    if real_votes:
        reasons.append(f"{real_votes} user report(s) say it's genuine.")
    if not (registry_verified or fake_votes or real_votes):
        reasons.append("No registry match and no user reports yet.")

    if fake_weight >= FAKE_THRESHOLD and fake_weight > real_weight:
        tier = "reported_fake"
        if registry_verified:
            reasons.append("Counterfeits often copy real registration numbers, so reports outweigh the registry match.")
    elif fake_weight >= DISPUTE_MIN_WEIGHT and real_weight >= DISPUTE_MIN_WEIGHT:
        tier = "disputed"
    elif registry_verified:
        tier = "verified"
    elif synthetic or not checksum_valid:
        tier = "suspicious"
    else:
        tier = "unverified"

    total = real_votes + fake_votes
    if total >= HIGH_CONFIDENCE_VOTES:
        confidence = "high"
    elif total >= MEDIUM_CONFIDENCE_VOTES:
        confidence = "medium"
    else:
        confidence = "low"

    return IntegrityResult(
        tier=tier,
        headline=HEADLINES[tier],
        reasons=reasons,
        confidence=confidence,
        real_votes=real_votes,
        fake_votes=fake_votes,
        real_weight=round(real_weight, 2),
        fake_weight=round(fake_weight, 2),
        checksum_valid=checksum_valid,
        nafdac_verified=nafdac_verified,
        manufacturer_verified=manufacturer_verified,
    )
