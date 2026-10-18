"""Turn consented, thumbs-up assistant answers into CANDIDATE knowledge entries.

Usage: python manage.py build_knowledge_base

This is the first step of "the AI learns from our users". It only reads what users
opted in to share (ChatMessage.training_ok) and rated helpful, scrubs personal
identifiers, and skips questions that talk about the user personally ("my blood
pressure", "I have diabetes") because those answers were tailored to one person and
shouldn't become general advice. Everything is created UNAPPROVED: an admin edits and
approves each entry in Django admin before the assistant is allowed to use it.
"""
import re

from django.core.management.base import BaseCommand

from apps.assistant.management.commands.export_training_data import scrub
from apps.assistant.models import ChatMessage
from apps.research.models import KnowledgeEntry

_PERSONAL = re.compile(r"\b(my|i|i'm|i've|i have|i am|me|mine|myself|we|our|us)\b", re.IGNORECASE)
MIN_QUESTION_WORDS = 4


class Command(BaseCommand):
    help = "Create unapproved knowledge-base candidates from consented, rated chats."

    def handle(self, *args, **options):
        created = skipped_personal = skipped_dupe = 0
        rated = ChatMessage.objects.filter(role="assistant", feedback=1, training_ok=True).select_related("thread")
        for answer in rated:
            question = (
                ChatMessage.objects.filter(thread=answer.thread, role="user", created_at__lte=answer.created_at, training_ok=True)
                .order_by("-created_at")
                .first()
            )
            if question is None or question.text == "(photo)" or question.image_count:
                continue
            text = scrub(question.text).strip()
            if len(text.split()) < MIN_QUESTION_WORDS or _PERSONAL.search(text):
                skipped_personal += 1
                continue
            if KnowledgeEntry.objects.filter(question__iexact=text).exists():
                skipped_dupe += 1
                continue
            KnowledgeEntry.objects.create(
                question=text[:500], answer=scrub(answer.text), source=KnowledgeEntry.Source.CHAT, approved=False
            )
            created += 1
        self.stdout.write(
            f"Created {created} candidate(s) (unapproved). Skipped {skipped_personal} personal/short, {skipped_dupe} duplicate. "
            "Review and approve them in Django admin > Knowledge entries."
        )
