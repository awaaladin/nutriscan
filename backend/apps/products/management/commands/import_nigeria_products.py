"""Bulk-import real Nigerian packaged-food products from Open Food Facts.

The live OFF database has ~500+ products tagged countries=nigeria -- real
barcodes with real nutrition data contributed by shoppers. Pulling that in
bulk gives the scanner actual local coverage instead of relying on a single
barcode guess landing on an entry that happens to exist.

The legacy bulk search endpoints (world.openfoodfacts.org/api/v2/search and
/cgi/search.pl) are both unreliable -- as of this writing the former 503s
unconditionally and the latter serves an HTML maintenance page with a 200
status. This uses OFF's newer search-a-licious service instead, which needs
the country tag quoted (`countries_tags:"en:nigeria"`) -- the unquoted form
silently matches zero results rather than erroring. Full nutrition per
barcode still goes through the existing OpenFoodFactsClient (same path a
live scan uses).

Usage: python manage.py import_nigeria_products [--limit N]
"""
import time

import requests
from django.core.management.base import BaseCommand

from apps.integrations.open_food_facts import OpenFoodFactsClient
from apps.products.models import Product

SEARCH_URL = "https://search.openfoodfacts.org/search"
HEADERS = {"User-Agent": "NutriScan/0.1 (contact: nutriscan-app@example.com)"}


class Command(BaseCommand):
    help = "Import Nigeria-tagged products from Open Food Facts into the local Product table."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=300, help="Max number of products to import this run.")
        parser.add_argument("--page-size", type=int, default=100, help="Barcodes fetched per search page.")

    def handle(self, *args, **options):
        limit = options["limit"]
        page_size = options["page_size"]
        client = OpenFoodFactsClient()

        barcodes = []
        page = 1
        while len(barcodes) < limit:
            products = None
            for attempt in range(4):
                try:
                    response = requests.get(
                        SEARCH_URL,
                        params={
                            "q": 'countries_tags:"en:nigeria"',
                            "page": page,
                            "page_size": page_size,
                            "fields": "code",
                        },
                        timeout=15,
                        headers=HEADERS,
                    )
                    response.raise_for_status()
                    products = response.json().get("hits", [])
                    break
                except requests.RequestException as exc:
                    wait = 3 * (attempt + 1)
                    self.stdout.write(f"Page {page} attempt {attempt + 1} failed ({exc}); retrying in {wait}s…")
                    time.sleep(wait)
            if products is None:
                self.stdout.write(f"Page {page} failed after retries; stopping pagination with {len(barcodes)} barcodes so far.")
                break
            if not products:
                break
            barcodes.extend(p["code"] for p in products if p.get("code"))
            page += 1
            time.sleep(1)

        barcodes = barcodes[:limit]
        self.stdout.write(f"Found {len(barcodes)} candidate barcodes. Fetching full product data…")

        created, updated, skipped = 0, 0, 0
        for i, barcode in enumerate(barcodes, start=1):
            # fetch_product() returns None for any non-200 (including a transient
            # 429/503 under load), so retry here rather than treating a rate-limit
            # blip the same as "this barcode genuinely has no data".
            off_data = None
            for attempt in range(3):
                off_data = client.fetch_product(barcode)
                if off_data is not None:
                    break
                time.sleep(2 * (attempt + 1))
            if off_data is None:
                skipped += 1
                continue
            _, was_created = Product.objects.update_or_create(
                barcode=barcode,
                defaults={"source": Product.Source.OPEN_FOOD_FACTS, **off_data},
            )
            if was_created:
                created += 1
            else:
                updated += 1
            if i % 25 == 0:
                self.stdout.write(f"...{i}/{len(barcodes)} processed (created={created} updated={updated} skipped={skipped})")
            time.sleep(0.8)
            if i % 50 == 0:
                time.sleep(5)

        self.stdout.write(self.style.SUCCESS(f"Done. created={created} updated={updated} skipped={skipped}"))
