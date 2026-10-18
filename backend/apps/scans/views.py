from rest_framework import status
from rest_framework.generics import DestroyAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Scan
from .serializers import ScanSerializer


class HistoryListView(ListAPIView):
    serializer_class = ScanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Newest first (Scan.Meta.ordering), capped so a long history stays quick:
        # each row carries the full product, including its trust assessment.
        return Scan.objects.filter(user=self.request.user).select_related("product")[:100]

    def delete(self, request):
        """Clear the user's whole history. Only THEIR record of what they scanned is removed:
        the products, their nutrition, trust evidence and corrections stay in the NutriScan
        data set, so nothing we learned is lost and nobody else is affected."""
        deleted, _ = Scan.objects.filter(user=request.user).delete()
        return Response({"deleted": deleted})


class HistoryDetailView(DestroyAPIView):
    """Remove one scan from the user's own history (never the product itself)."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Scan.objects.filter(user=self.request.user)
