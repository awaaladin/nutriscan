from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.subscriptions.services import refresh_pro_status

from .serializers import DeleteAccountSerializer, PreferencesSerializer, RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": PreferencesSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=201,
        )


class PreferencesView(generics.RetrieveUpdateAPIView):
    serializer_class = PreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Re-checks Pro against Google when a stored expiry has passed, so
        # renewals and lapses show up without needing a push webhook.
        refresh_pro_status(self.request.user)
        return self.request.user


class DeleteAccountView(APIView):
    """DELETE /api/user/account/ with {"password": ...} -- erases the account and everything
    personal in it (profile, health notes, readings, chats, scans, reports). Payment and AI cost
    records are kept, detached from the person, because the law requires financial records."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            return Response({"detail": "That password isn't right."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
