"""The research step: find independent evidence about a product and cross-check it.

Sources, in order of how much they are trusted:
  1. Open Food Facts, matched by name, brand AND country (see matching.py)
  2. AI web research, but only when live web search ran and cited pages (web_ai.py);
     AI answering from memory is never saved as evidence

Conservative rules, because wrong data costs more trust than missing data:
  - A source from the wrong country is stored as REFERENCE and never compared.
  - Existing values are never overwritten.
  - Blanks are filled ONLY when the source agrees with what we already hold on at
    least two fields (that overlap is what shows it is the same product) and
    conflicts on none. A lone source with nothing to compare stays a suggestion.
  - A strong conflict is not "fixed": it becomes an open correction for review.
"""
import re
from typing import Dict, List

from apps.products.models import Product

from . import off, web_ai
from .matching import KEY_FIELDS, MATCH_THRESHOLD, agreement, barcode_country, match_score, values_agree
from .models import DataCorrection, ProductEvidence, ResearchRun
from .trust import data_trust

MAX_EVIDENCE_PER_RUN = 4
MIN_AGREEING_FIELDS = 2
MIN_CONFLICTING_FIELDS = 2
STRONG_MATCH = 0.9  # name, brand and country all line up


def _ours(product: Product) -> Dict[str, float]:
    return {f: getattr(product, f) for f in KEY_FIELDS if getattr(product, f) is not None}


def _query(product: Product) -> str:
    text = f"{product.brand} {product.name}".strip()
    return re.sub(r"\s+", " ", off.clean_text(text))


def _record(product, source_type, ref, label, facts, score, status, note="") -> ProductEvidence:
    return ProductEvidence.objects.create(
        product=product, source_type=source_type, source_ref=ref[:500], source_label=label[:200],
        facts=facts, match_score=score, status=status, note=note[:300],
    )


def _evaluate_source(product: Product, source_type, ref, label, facts, ingredients, score, result) -> None:
    """Compare one matched source with our data and record what it means."""
    if ProductEvidence.objects.filter(product=product, source_type=source_type, source_ref=ref[:500]).exists():
        return  # already recorded on an earlier run
    payload = {**facts, **({"ingredients_text": ingredients} if ingredients else {})}

    if score < MATCH_THRESHOLD:
        _record(product, source_type, ref, label, payload, score, ProductEvidence.Status.REFERENCE,
                "Different country or weak match: kept for reference, not used.")
        result["evidence"] += 1
        return

    agree, conflict, compared = agreement(_ours(product), facts)
    if compared >= MIN_CONFLICTING_FIELDS and conflict >= MIN_CONFLICTING_FIELDS:
        _record(product, source_type, ref, label, payload, score, ProductEvidence.Status.CONFLICTS,
                f"{conflict} of {compared} compared values differ.")
        result["evidence"] += 1
        result["conflicts"].append(label)
        for field in KEY_FIELDS:
            mine, theirs = getattr(product, field), facts.get(field)
            if mine is not None and theirs is not None:
                if not values_agree(field, mine, theirs) and not DataCorrection.objects.filter(
                    product=product, field=field, status=DataCorrection.Status.OPEN, user__isnull=True
                ).exists():
                    DataCorrection.objects.create(
                        product=product, user=None, field=field, current_value=str(mine), suggested_value=str(theirs),
                        reason=f"Research: {label} lists {theirs}",
                    )
        return

    if agree >= MIN_AGREEING_FIELDS and conflict == 0:
        applied = []
        for field in KEY_FIELDS:
            if getattr(product, field) is None and facts.get(field) is not None:
                setattr(product, field, facts[field])  # only blanks: what we hold is never overwritten
                applied.append(field)
        if ingredients and not product.ingredients_text.strip():
            product.ingredients_text = ingredients
            applied.append("ingredients_text")
        if applied:
            product.is_estimated = True  # part of the record is now inherited
            product.save()
            result["applied"].extend(applied)
        _record(product, source_type, ref, label, payload, score,
                ProductEvidence.Status.APPLIED if applied else ProductEvidence.Status.AGREES,
                f"Agrees on {agree} of {compared} compared values.")
        result["evidence"] += 1
        return

    # A near-certain match (name, brand and country) that agrees on the one value we can
    # compare is real corroboration of our data -- but one field is too little to copy
    # other values from, so nothing is filled in.
    if agree >= 1 and conflict == 0 and score >= STRONG_MATCH:
        _record(product, source_type, ref, label, payload, score, ProductEvidence.Status.AGREES,
                f"Agrees on {agree} of {compared} compared value(s); too few to fill in others.")
        result["evidence"] += 1
        return

    # Matches the product but there is nothing to cross-check against: a suggestion only.
    _record(product, source_type, ref, label, payload, score, ProductEvidence.Status.SUGGESTED,
            "Single source with nothing to cross-check; not applied.")
    result["evidence"] += 1


def research_product(product: Product) -> dict:
    """Run research for one product and report what happened."""
    result = {"evidence": 0, "applied": [], "conflicts": [], "skipped": []}
    if product.product_type != Product.ProductType.FOOD:
        result["skipped"].append("Not a packaged food.")
        ResearchRun.objects.create(product=product)
        return {**result, "trust": data_trust(product)}

    country = barcode_country(product.barcode)
    query = _query(product)
    candidates = off.search(query) if query else []
    scored = sorted(
        (
            (match_score(product.name, product.brand, country, c["name"], c["brands"], c["countries"]), c)
            for c in candidates
            if c["code"] != product.barcode  # the exact barcode is handled by the normal scan path
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    for score, c in scored[:MAX_EVIDENCE_PER_RUN]:
        label = f"{c['name']} ({', '.join(x.replace('en:', '') for x in c['countries'][:2]) or 'country unknown'})"
        _evaluate_source(product, "open_food_facts", c["url"], label, c["facts"], c["ingredients_text"], score, result)

    web = web_ai.research(product)
    if web is None:
        result["skipped"].append("AI web research isn't available, so only database sources were used.")
    else:
        _evaluate_source(product, "web_ai", web["url"], web["label"], web["facts"], web.get("ingredients", ""), web["score"], result)

    ResearchRun.objects.create(product=product, evidence_added=result["evidence"], fields_applied=result["applied"])
    product.refresh_from_db()
    return {**result, "trust": data_trust(product)}
