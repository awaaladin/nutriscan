"""Export assistant conversations as a training/evaluation dataset.

Only what the user explicitly consented to is ever exported:
  - messages written while `allow_training_use` was on (ChatMessage.training_ok;
    withdrawing consent clears it on all of the user's messages);
  - conversations whose assistant answers the user rated.

What happens to it before it leaves the database:
  - no user ids, usernames or health notes -- each thread gets a random label;
  - emails, phone numbers and any long digit string (account/ID/BVN/NIN-like)
    are replaced with placeholders;
  - photos were never stored, so they can't be exported.
Scrubbing is best-effort: names and free-form details can survive, so review the
file before using it for anything. Output (two JSONL files):
  - `good.jsonl`    threads with at least one thumbs-up answer: candidate training pairs
  - `review.jsonl`  answers rated thumbs-down, with the user's note: what to fix

Usage: python manage.py export_training_data --out ./training
"""
import json
import os
import re
import uuid

from django.core.management.base import BaseCommand

from apps.assistant.models import ChatMessage, ChatThread

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?234|0)[\s-]?[789][01]\d[\s-]?\d{3}[\s-]?\d{4}")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{9,}(?!\d)")


def scrub(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    return _LONG_NUMBER.sub("[number]", text)


class Command(BaseCommand):
    help = "Export consented, anonymised assistant chats as JSONL training/review data."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="./training", help="Output directory.")

    def handle(self, *args, **options):
        os.makedirs(options["out"], exist_ok=True)
        good, review = [], []
        threads = ChatThread.objects.filter(messages__training_ok=True).distinct()
        for thread in threads:
            messages = list(thread.messages.filter(training_ok=True))
            label = uuid.uuid4().hex[:12]
            turns = [{"role": m.role, "content": scrub(m.text)} for m in messages]
            if any(m.role == "assistant" and m.feedback == 1 for m in messages):
                good.append({"thread": label, "messages": turns})
            for position, m in enumerate(messages):
                if m.role == "assistant" and m.feedback == -1:
                    review.append(
                        {
                            "thread": label,
                            "context": turns[: position + 1],
                            "note": scrub(m.feedback_note),
                        }
                    )
        for name, rows in (("good.jsonl", good), ("review.jsonl", review)):
            with open(os.path.join(options["out"], name), "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.stdout.write(f"Exported {len(good)} good threads and {len(review)} answers to review to {options['out']}.")
