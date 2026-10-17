"""Helpers for the photo-identify flow (see IdentifyProductView).

The rule that drives all of this: check our own data before paying for AI.
A barcode already on file, or a NAFDAC number already on file, must be
answered from the database."""
from typing import List, Optional, Tuple

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Product

MAX_PHOTOS = 6
MAX_PHOTO_BYTES = 5 * 1024 * 1024

_NUTRITION_FIELDS = (
    "calories_kcal", "sugar_g", "saturated_fat_g", "sodium_mg",
    "carbohydrates_g", "fiber_g", "protein_g",
)


def read_valid_photos(files) -> List[Tuple[bytes, str]]:
    """Returns (bytes, mime) per upload, or raises ValueError with a message
    for the user. ImageField validation confirms each is a real image."""
    if len(files) > MAX_PHOTOS:
        raise ValueError(f"Please send at most {MAX_PHOTOS} photos.")
    image_field = serializers.ImageField()
    photos = []
    for index, upload in enumerate(files, start=1):
        if upload.size > MAX_PHOTO_BYTES:
            raise ValueError(f"Photo {index} is larger than 5MB. Retake it or choose a smaller one.")
        try:
            image_field.run_validation(upload)
        except (serializers.ValidationError, DjangoValidationError):
            raise ValueError(f"Photo {index} isn't a valid image. Please retake it.")
        upload.seek(0)
        photos.append((upload.read(), upload.content_type or "image/jpeg"))
    return photos


def inherit_nafdac_verification(product: Product) -> Product:
    """If an admin already confirmed this NAFDAC number on another product
    (e.g. another pack size of the same registration), this one is covered by
    the same registry check -- no new check needed."""
    if product.nafdac_number and not product.nafdac_verified:
        if Product.objects.filter(nafdac_number=product.nafdac_number, nafdac_verified=True).exclude(pk=product.pk).exists():
            product.nafdac_verified = True
            product.save(update_fields=["nafdac_verified"])
    return product


def product_for_nafdac(nafdac_number: str) -> Optional[Product]:
    """Best existing product carrying this NAFDAC number: prefer verified,
    then non-estimated, so a copy never starts from a shakier record."""
    return (
        Product.objects.filter(nafdac_number=nafdac_number)
        .order_by("-nafdac_verified", "is_estimated", "-updated_at")
        .first()
    )


def copy_from_twin(barcode: str, twin: Product) -> Product:
    """New product for `barcode` that shares a NAFDAC registration with `twin`
    (the user supplied both at once). Always marked estimated: we're trusting
    that this barcode belongs to that registered product."""
    product = Product.objects.create(
        barcode=barcode,
        name=twin.name,
        brand=twin.brand,
        source=Product.Source.COMMUNITY,
        product_type=twin.product_type,
        is_estimated=True,
        nafdac_number=twin.nafdac_number,
        nafdac_verified=twin.nafdac_verified,
        manufacturer_verified=False,
        ingredients_text=twin.ingredients_text,
        additives=twin.additives,
        image_url=twin.image_url,
        **{field: getattr(twin, field) for field in _NUTRITION_FIELDS},
    )
    return product


# --- Borrowing nutrition from a matching product in our own data -------------------------
#
# The same registered product is often on file more than once (another barcode for a
# different pack size, or an earlier photo scan). If one copy has a nutrition table and
# another doesn't, the empty one should pick it up from our data rather than stay blank
# or ask the user -- nutrition per 100g is the same across pack sizes of one product.

_KEY_NUTRIENTS = ("sugar_g", "saturated_fat_g", "sodium_mg")
_FILLABLE = _NUTRITION_FIELDS
MATCH_THRESHOLD = 0.8  # name similarity needed when there is no shared NAFDAC number
_STOP_WORDS = {"the", "and", "of", "with", "flavour", "flavor", "flavoured", "flavored", "pack", "pcs"}


def _tokens(*texts: str) -> set:
    import re

    words = set()
    for text in texts:
        words.update(re.findall(r"[a-z0-9]+", (text or "").lower()))
    return words - _STOP_WORDS


def _known_key_nutrients(product: Product) -> int:
    return sum(getattr(product, field) is not None for field in _KEY_NUTRIENTS)


def similar_products_with_nutrition(product: Product) -> List[Product]:
    """Other products that are very likely the same registered product AND have at
    least two of the three key nutrients, best match first: a shared NAFDAC number,
    then a near-identical name under the same brand."""
    candidates = Product.objects.exclude(pk=product.pk).filter(product_type=product.product_type)
    matches = []
    for other in candidates:
        if _known_key_nutrients(other) < 2:
            continue
        if product.nafdac_number and other.nafdac_number == product.nafdac_number:
            matches.append((2.0, other))
            continue
        if not product.brand or product.brand.strip().lower() != (other.brand or "").strip().lower():
            continue
        mine, theirs = _tokens(product.name), _tokens(other.name)
        if mine and theirs:
            similarity = len(mine & theirs) / len(mine | theirs)
            if similarity >= MATCH_THRESHOLD:
                matches.append((similarity, other))
    # prefer verified data, then more complete data, then the closest match
    matches.sort(key=lambda m: (not m[1].is_estimated, _known_key_nutrients(m[1]), m[0]), reverse=True)
    return [other for _, other in matches]


def borrow_nutrition(product: Product) -> bool:
    """Fill this product's missing nutrition from a matching product on file.
    Only blanks are filled, never existing values. Returns True if anything changed.
    The result is marked estimated: it is inherited data, not read from this pack."""
    if product.product_type != Product.ProductType.FOOD or _known_key_nutrients(product) == len(_KEY_NUTRIENTS):
        return False
    twins = similar_products_with_nutrition(product)
    if not twins:
        return False

    changed = False
    for twin in twins:  # best first; later twins only fill what is still blank
        for field in _FILLABLE:
            if getattr(product, field) is None and getattr(twin, field) is not None:
                setattr(product, field, getattr(twin, field))
                changed = True
        if not product.ingredients_text.strip() and twin.ingredients_text.strip():
            product.ingredients_text = twin.ingredients_text
            changed = True
        if _known_key_nutrients(product) == len(_KEY_NUTRIENTS):
            break
    if changed:
        product.is_estimated = True
        product.save()
    return changed
