"""Is there enough trusted data to train our own model yet?

Usage: python manage.py dataset_readiness

Prints how big the data set is and what is still missing before fine-tuning a
smaller model would beat the cloud AI we already use. Fine-tuning on too little
data makes a model WORSE (it forgets what it knew and memorises the few examples),
so the thresholds below are deliberate, not a formality.
"""
from django.core.management.base import BaseCommand

from apps.assistant.models import ChatMessage
from apps.products.models import Product
from apps.research.models import DataCorrection, KnowledgeEntry, ProductEvidence
from apps.research.trust import data_trust

# Rough minimums from fine-tuning practice for a narrow assistant.
KNOWLEDGE_MIN = 1000
KNOWLEDGE_GOOD = 5000
PRODUCTS_MIN = 500


class Command(BaseCommand):
    help = "Report dataset size and readiness for fine-tuning."

    def handle(self, *args, **options):
        out = self.stdout.write
        levels = {"verified": 0, "corroborated": 0, "sourced": 0, "unverified": 0}
        products = list(Product.objects.filter(product_type="food"))
        for product in products:
            levels[data_trust(product)["level"]] += 1
        trusted = levels["verified"] + levels["corroborated"]

        approved = KnowledgeEntry.objects.filter(approved=True).count()
        pending = KnowledgeEntry.objects.filter(approved=False).count()
        consented_rated = ChatMessage.objects.filter(role="assistant", training_ok=True, feedback=1).count()
        corrections = DataCorrection.objects.filter(status="accepted").count()

        out("PRODUCT DATA SET")
        out(f"  food products: {len(products)}")
        for name, count in levels.items():
            out(f"    {name:13} {count}")
        out(f"  evidence records: {ProductEvidence.objects.count()}, accepted user corrections: {corrections}")
        out("KNOWLEDGE BASE (what the assistant learns from)")
        out(f"  approved entries: {approved}   waiting for review: {pending}")
        out(f"  consented chat answers rated helpful: {consented_rated}")
        out("READINESS FOR A FINE-TUNED MODEL")
        out(f"  approved Q&A: {approved} / {KNOWLEDGE_MIN} minimum ({KNOWLEDGE_GOOD}+ recommended)  -> {'OK' if approved >= KNOWLEDGE_MIN else 'not yet'}")
        out(f"  trusted products: {trusted} / {PRODUCTS_MIN} minimum  -> {'OK' if trusted >= PRODUCTS_MIN else 'not yet'}")
        if approved >= KNOWLEDGE_MIN and trusted >= PRODUCTS_MIN:
            out("VERDICT: enough data to try a fine-tune. Export with export_knowledge_base and hold back 10% to evaluate it.")
        else:
            out(
                "VERDICT: NOT READY. Keep growing the reviewed data set; until then the assistant improves by retrieving "
                "from it (no training needed), which is more accurate than a model trained on this little data."
            )
