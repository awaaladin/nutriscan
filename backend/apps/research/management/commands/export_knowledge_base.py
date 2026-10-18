"""Export the approved knowledge base as training-ready JSONL.

Usage: python manage.py export_knowledge_base --out ./knowledge.jsonl [--format chat|qa]

Only APPROVED entries (reviewed by a person) are exported. Formats:
  chat  {"messages": [{"role":"user",...},{"role":"model",...}]}  for fine-tuning chat models
  qa    {"question":..., "answer":..., "topic":...}                for evaluation or other tools
"""
import json

from django.core.management.base import BaseCommand

from apps.research.models import KnowledgeEntry


class Command(BaseCommand):
    help = "Export approved knowledge entries as JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="./knowledge.jsonl")
        parser.add_argument("--format", choices=["chat", "qa"], default="chat")

    def handle(self, *args, **options):
        rows = 0
        with open(options["out"], "w", encoding="utf-8") as handle:
            for entry in KnowledgeEntry.objects.filter(approved=True).order_by("id"):
                if options["format"] == "chat":
                    row = {"messages": [{"role": "user", "content": entry.question}, {"role": "model", "content": entry.answer}]}
                else:
                    row = {"question": entry.question, "answer": entry.answer, "topic": entry.topic}
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows += 1
        self.stdout.write(f"Exported {rows} approved entries to {options['out']}.")
