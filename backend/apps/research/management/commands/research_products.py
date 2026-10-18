"""Cross-check products against other sources in bulk.

Usage: python manage.py research_products [--limit 50] [--days 7]

Picks food products that aren't verified and haven't been researched recently,
runs the same research step the app triggers, and prints what happened. Safe to
run repeatedly (and from a scheduler): evidence is never duplicated and existing
values are never overwritten.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.products.models import Product
from apps.research.agent import research_product


class Command(BaseCommand):
    help = "Research unverified products against Open Food Facts (and AI web search when available)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--days", type=int, default=7, help="Skip products researched within this many days.")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        candidates = (
            Product.objects.filter(product_type=Product.ProductType.FOOD, nafdac_verified=False, manufacturer_verified=False)
            .exclude(research_runs__created_at__gte=cutoff)
            .distinct()[: options["limit"]]
        )
        total = applied = conflicts = 0
        for product in candidates:
            outcome = research_product(product)
            total += 1
            applied += len(outcome["applied"])
            conflicts += len(outcome["conflicts"])
            self.stdout.write(
                f"{product.barcode} {product.name[:40]!r}: {outcome['evidence']} evidence, "
                f"applied {outcome['applied'] or '-'}, trust {outcome['trust']['level']}"
            )
        self.stdout.write(f"Researched {total} products: {applied} values applied, {conflicts} conflicts raised for review.")
