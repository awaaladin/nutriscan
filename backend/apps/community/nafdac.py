"""NAFDAC registration number handling.

NAFDAC publishes the Greenbook as a search site (greenbook.nafdac.gov.ng) but
no official API, so numbers are only *captured* and format-checked here; an
admin confirms them against the Greenbook before a product counts as
verified (see ProductAdmin actions). Formats vary by product type, e.g.
"A4-1234", "04-8861", "B1-6789L", so this check is deliberately loose -- it
filters obvious junk, it doesn't prove registration.
"""
import re
from typing import Optional

_PATTERN = re.compile(r"^[A-Z0-9]{1,3}-\d{3,6}[A-Z]?$")

GREENBOOK_URL = "https://greenbook.nafdac.gov.ng"


def normalize_nafdac_number(raw: Optional[str]) -> Optional[str]:
    """Uppercased, whitespace/dash-normalised number, or None if it isn't
    plausibly NAFDAC-shaped."""
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw.strip().upper()).replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"^(NAFDAC|NRN|REG\.?NO\.?)[:#]*", "", cleaned)
    return cleaned if _PATTERN.match(cleaned) else None
