from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.subscriptions.services import refresh_pro_status

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import render
from rest_framework.throttling import ScopedRateThrottle

from . import mailer, password_reset
from .serializers import DeleteAccountSerializer, PreferencesSerializer, RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        mailer.send_welcome(user)  # after commit; an email problem never blocks signup
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


class PasswordResetRequestView(APIView):
    """Always answers 200, so nobody can use it to find out which emails have accounts."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password-reset"

    def post(self, request):
        password_reset.request_reset(request.data.get("email", ""))
        return Response({"detail": "If that email has an account, we sent a link to reset the password."})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password-reset"

    def post(self, request):
        try:
            password_reset.confirm_reset(
                request.data.get("uid", ""), request.data.get("token", ""), request.data.get("password", "")
            )
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Password changed. You can sign in now."})


def reset_password_page(request, uid, token):
    """The page the emailed link opens in the phone browser."""
    if password_reset.user_for(uid, token) is None:
        return render(request, "users/reset_password.html", {"invalid": True}, status=400)
    errors = []
    if request.method == "POST":
        password, confirm = request.POST.get("password", ""), request.POST.get("confirm", "")
        if password != confirm:
            errors.append("The two passwords do not match.")
        else:
            try:
                password_reset.confirm_reset(uid, token, password)
                return render(request, "users/reset_password.html", {"done": True})
            except DjangoValidationError as exc:
                errors.extend(exc.messages)
    return render(request, "users/reset_password.html", {"errors": errors})


def forgot_password_page(request):
    """The page the app opens from its "Forgot password?" link: asks for the email and sends the reset link."""
    from django.http import HttpResponseNotAllowed

    if request.method not in ("GET", "POST"):
        return HttpResponseNotAllowed(["GET", "POST"])
    from django.core.cache import cache

    sent = False
    if request.method == "POST":
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        key = f"forgot-page:{forwarded or request.META.get('REMOTE_ADDR', '')}"
        tries = cache.get(key, 0)
        if tries < 10:  # an open "send an email" form must not be usable to flood someone's inbox
            cache.set(key, tries + 1, 3600)
            password_reset.request_reset(request.POST.get("email", ""))
        sent = True  # the same answer whether or not the address has an account (or we declined to send)
    return render(request, "users/forgot_password.html", {"sent": sent})
