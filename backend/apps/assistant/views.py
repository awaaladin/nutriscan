from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.integrations.gemini_chat import generate
from apps.integrations.vision_identify import IdentifyError
from apps.products.identify_helpers import read_valid_photos

from .context import build_context, emergency_notice
from .models import ChatMessage, ChatThread
from .prompts import SYSTEM_INSTRUCTION

MAX_MESSAGE_CHARS = 1000
MAX_IMAGES = 3
HISTORY_TURNS = 10
THREAD_LIST_LIMIT = 50


def message_data(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "text": message.text,
        "image_count": message.image_count,
        "web_research": message.web_research,
        "sources": message.sources,
        "feedback": message.feedback,
        "created_at": message.created_at,
    }


class ChatSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, max_length=MAX_MESSAGE_CHARS)
    thread_id = serializers.IntegerField(required=False, allow_null=True)


class ChatView(APIView):
    """POST /api/assistant/chat/ -- one turn of the user's conversation.

    Multipart: `message` (text), optional `thread_id` (omit to start a new chat),
    optional `images` (up to 3 photos: a food pack, nutrition table, medicine box...).
    Earlier turns are loaded from the database, so the client sends only the new
    message. Photos go to the AI for this one answer and are not stored."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def post(self, request):
        serializer = ChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = (serializer.validated_data.get("message") or "").strip()
        uploads = request.FILES.getlist("images")[:MAX_IMAGES]
        if not text and not uploads:
            return Response(
                {"detail": "Type a question or attach a photo.", "reason": "empty_message"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notice = emergency_notice(text)

        thread = None
        thread_id = serializer.validated_data.get("thread_id")
        if thread_id:
            thread = get_object_or_404(ChatThread, pk=thread_id, user=request.user)

        try:
            photos = read_valid_photos(uploads) if uploads else []
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "reason": "bad_photos", "notice": notice}, status=status.HTTP_400_BAD_REQUEST
            )

        history = []
        if thread:
            earlier = list(thread.messages.order_by("-created_at", "-id")[:HISTORY_TURNS])[::-1]
            history = [
                {
                    "role": m.role,
                    "text": m.text + (f" [the user attached {m.image_count} photo(s)]" if m.image_count else ""),
                }
                for m in earlier
            ]

        context = build_context(request.user, text)
        try:
            reply = generate(SYSTEM_INSTRUCTION + "\n\n" + context, history, text, photos)
        except IdentifyError as exc:
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE if exc.reason == "ai_not_configured" else status.HTTP_502_BAD_GATEWAY
            )
            return Response({"detail": exc.message, "reason": exc.reason, "notice": notice}, status=http_status)

        training_ok = request.user.allow_training_use
        with transaction.atomic():
            if thread is None:
                thread = ChatThread.objects.create(user=request.user, title=(text or "Photo question")[:60])
            ChatMessage.objects.create(
                thread=thread, role="user", text=text or "(photo)", image_count=len(photos), training_ok=training_ok
            )
            answer = ChatMessage.objects.create(
                thread=thread, role="assistant", text=reply["answer"], web_research=reply["web_research"],
                sources=reply["sources"], training_ok=training_ok,
            )
            thread.save(update_fields=["updated_at"])

        return Response(
            {"thread_id": thread.id, "title": thread.title, "message": message_data(answer), "notice": notice}
        )


class ThreadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        threads = ChatThread.objects.filter(user=request.user)[:THREAD_LIST_LIMIT]
        return Response(
            [{"id": t.id, "title": t.title or "New chat", "updated_at": t.updated_at} for t in threads]
        )

    def delete(self, request):
        """Delete every conversation this user has (their right to erase their data)."""
        deleted, _ = ChatThread.objects.filter(user=request.user).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


class ThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        thread = get_object_or_404(ChatThread, pk=thread_id, user=request.user)
        return Response(
            {"id": thread.id, "title": thread.title, "messages": [message_data(m) for m in thread.messages.all()]}
        )

    def delete(self, request, thread_id):
        get_object_or_404(ChatThread, pk=thread_id, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedbackSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=[-1, 0, 1])
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)


class FeedbackView(APIView):
    """Thumbs up/down on an assistant answer (0 clears it). Rated answers are what
    the consented training export is built from."""

    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        message = get_object_or_404(ChatMessage, pk=message_id, thread__user=request.user, role="assistant")
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["value"]
        message.feedback = value or None
        message.feedback_note = serializer.validated_data.get("note", "") if value else ""
        message.save(update_fields=["feedback", "feedback_note"])
        return Response({"id": message.id, "feedback": message.feedback})


class SettingsSerializer(serializers.Serializer):
    health_notes = serializers.CharField(required=False, allow_blank=True, max_length=500)
    allow_training_use = serializers.BooleanField(required=False)


class AssistantSettingsView(APIView):
    """What the assistant knows about you, and whether your chats may help train
    NutriScan. Withdrawing consent immediately removes all your messages from any
    future export."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _data(user):
        return {"health_notes": user.health_notes, "allow_training_use": user.allow_training_use}

    def get(self, request):
        return Response(self._data(request.user))

    def patch(self, request):
        serializer = SettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        data = serializer.validated_data
        if "health_notes" in data:
            user.health_notes = data["health_notes"].strip()
        if "allow_training_use" in data:
            user.allow_training_use = data["allow_training_use"]
            if not user.allow_training_use:
                ChatMessage.objects.filter(thread__user=user).update(training_ok=False)
        user.save(update_fields=["health_notes", "allow_training_use"])
        return Response(self._data(user))
