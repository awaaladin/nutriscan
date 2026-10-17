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
