from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Scan
from .serializers import ScanSerializer


class HistoryListView(ListAPIView):
    serializer_class = ScanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Newest first (Scan.Meta.ordering), capped so a long history stays quick:
        # each row carries the full product, including its trust assessment.
        return Scan.objects.filter(user=self.request.user).select_related("product")[:100]
