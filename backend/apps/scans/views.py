from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Scan
from .serializers import ScanSerializer


class HistoryListView(ListAPIView):
    serializer_class = ScanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Scan.objects.filter(user=self.request.user).select_related("product")
