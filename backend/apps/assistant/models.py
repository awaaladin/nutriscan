"""The user's private conversations with the NutriScan assistant.

These can contain health information, so:
- they belong to one account and are only ever returned to it;
- attached photos are sent to the AI for that one answer and are NOT stored,
  only how many were attached;
- they are deliberately NOT registered in Django admin, so staff can't browse
  them. The only way they leave the account is the consented, anonymised export
  (`manage.py export_training_data`), which requires the user's opt-in.
"""
from django.conf import settings
from django.db import models


class ChatThread(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_threads")
    title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"ChatThread({self.pk}, user={self.user_id})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField()
    image_count = models.PositiveSmallIntegerField(default=0)
    web_research = models.BooleanField(default=False)
    sources = models.JSONField(default=list, blank=True)
    # The user's rating of an assistant answer: 1 = helpful, -1 = not, None = unrated.
    feedback = models.SmallIntegerField(null=True, blank=True)
    feedback_note = models.CharField(max_length=300, blank=True)
    # Snapshot of the user's training consent when the message was written; cleared
    # for all their messages if they withdraw consent.
    training_ok = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"ChatMessage({self.pk}, {self.role})"
