"""Real profit and loss for one month: what members paid, minus Paystack's fees and Gemini's bill.

Usage: python manage.py ai_cost_report [--month 2026-11]

Revenue is counted when it was paid (a yearly plan counts in full in its month). AI cost is
worked out from Gemini's own token counts for every call (AiUsage) at the prices in
settings.GEMINI_PRICES_USD_PER_MILLION, converted at USD_NGN_RATE; compare it with the Google
Cloud bill and adjust those settings if they drift. Hosting (Vercel, Neon) is not included.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum
from django.utils import timezone

from apps.subscriptions.models import AiUsage, PaystackPayment


def paystack_fee_ngn(amount_ngn: float) -> float:
    """Paystack's local card fee: 1.5%, plus N100 from N2,500 up, capped at N2,000."""
    fee = amount_ngn * 0.015 + (100 if amount_ngn >= 2500 else 0)
    return min(fee, 2000)


class Command(BaseCommand):
    help = "Show one month's revenue, Paystack fees, AI cost and profit, per plan."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="YYYY-MM (default: this month)")

    def handle(self, *args, **options):
        now = timezone.localtime()
        try:
            start = (datetime.strptime(options["month"], "%Y-%m") if options["month"] else now.replace(tzinfo=None))
        except ValueError:
            raise CommandError("Use --month YYYY-MM")
        start = timezone.make_aware(start.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        end = timezone.make_aware((start.replace(tzinfo=None).replace(day=28) + timedelta(days=4)).replace(day=1))
        rate = settings.USD_NGN_RATE

        revenue, fees, buyers = defaultdict(float), defaultdict(float), defaultdict(int)
        for p in PaystackPayment.objects.filter(status="success", paid_at__gte=start, paid_at__lt=end):
            key = "top-ups" if p.kind == "credits" else (p.tier or "pro")
            naira = p.amount_kobo / 100
            revenue[key] += naira
            fees[key] += paystack_fee_ngn(naira)
            buyers[key] += 1

        usage = (
            AiUsage.objects.filter(created_at__gte=start, created_at__lt=end)
            .values("tier")
            .annotate(cost=Sum("cost_usd"), calls=Count("id"), users=Count("user", distinct=True),
                      credits=Sum("credits"), bonus=Sum("bonus_credits"))
        )
        ai = {(u["tier"] or "free"): u for u in usage}

        self.stdout.write(f"NutriScan, {start:%B %Y} (N{rate:,.0f} = $1)\n")
        rows = ["free", "pro", "plus", "care", "top-ups"]
        header = f"{'':10}{'payments':>9}{'revenue':>12}{'paystack':>10}{'AI users':>9}{'AI calls':>9}{'AI cost':>10}{'profit':>12}"
        self.stdout.write(header)
        totals = defaultdict(float)
        for key in rows:
            u = ai.get(key, {})
            cost = float(u.get("cost") or 0) * rate
            profit = revenue[key] - fees[key] - cost
            for name, value in (("revenue", revenue[key]), ("fees", fees[key]), ("cost", cost), ("profit", profit)):
                totals[name] += value
            self.stdout.write(
                f"{key:10}{buyers[key]:>9}{revenue[key]:>12,.0f}{fees[key]:>10,.0f}{u.get('users', 0):>9}"
                f"{u.get('calls', 0):>9}{cost:>10,.0f}{profit:>12,.0f}"
            )
        self.stdout.write(
            f"{'TOTAL':10}{sum(buyers.values()):>9}{totals['revenue']:>12,.0f}{totals['fees']:>10,.0f}{'':>9}{'':>9}"
            f"{totals['cost']:>10,.0f}{totals['profit']:>12,.0f}"
        )

        by_action = (
            AiUsage.objects.filter(created_at__gte=start, created_at__lt=end)
            .values("action").annotate(calls=Count("id"), cost=Sum("cost_usd"), tokens_in=Sum("prompt_tokens"),
                                       tokens_out=Sum("output_tokens"), searches=Sum("search_queries"))
            .order_by("-cost")
        )
        self.stdout.write("\nPer AI action: calls, average naira per call, tokens in/out per call, searches")
        for a in by_action:
            calls = a["calls"] or 1
            self.stdout.write(
                f"  {a['action']:16}{a['calls']:>7}   N{float(a['cost'] or 0) * rate / calls:>6.2f}"
                f"   {a['tokens_in'] // calls:>6} / {a['tokens_out'] // calls:<6}{a['searches']:>6}"
            )
