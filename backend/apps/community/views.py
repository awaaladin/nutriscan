from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.models import Product

from .models import ProductReport, ReportFlag, ReportPhoto
from .serializers import (
    MAX_PHOTO_BYTES,
    MAX_PHOTOS_PER_REPORT,
    ProductReportSerializer,
    ReportCreateSerializer,
    ReportFlagSerializer,
)
from .services import integrity_dict


class ProductReportsView(APIView):
    """GET lists a product's visible reports plus its integrity percentage.
    POST creates the caller's report, or updates it if they already filed one
    (one verdict per user per product). Photos are multipart `photos` parts and
    append to any already attached, up to MAX_PHOTOS_PER_REPORT total."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, barcode):
        product = get_object_or_404(Product, barcode=barcode)
        reports = (
            ProductReport.objects.filter(product=product, is_hidden=False)
            .select_related("user")
            .prefetch_related("photos")
        )
        return Response(
            {
                "integrity": integrity_dict(product),
                "reports": ProductReportSerializer(reports, many=True, context={"request": request}).data,
            }
        )

    def post(self, request, barcode):
        product = get_object_or_404(Product, barcode=barcode)
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        photos = request.FILES.getlist("photos")
        image_field = serializers.ImageField()
        for photo in photos:
            if photo.size > MAX_PHOTO_BYTES:
                return Response({"detail": "Each photo must be 5MB or smaller."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                image_field.run_validation(photo)  # model save doesn't verify it's a real image
            except (serializers.ValidationError, DjangoValidationError):
                return Response({"detail": "Uploaded files must be valid images."}, status=status.HTTP_400_BAD_REQUEST)
            photo.seek(0)

        existing = ProductReport.objects.filter(product=product, user=request.user).first()
        already_attached = existing.photos.count() if existing else 0
        if already_attached + len(photos) > MAX_PHOTOS_PER_REPORT:
            return Response(
                {"detail": f"A report can have at most {MAX_PHOTOS_PER_REPORT} photos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report, created = ProductReport.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                "verdict": data["verdict"],
                "comment": data.get("comment", ""),
                "where_bought": data.get("where_bought", ""),
                "batch_number": data.get("batch_number", ""),
            },
        )
        for photo in photos:
            # ImageField validates that the upload is a real image.
            ReportPhoto.objects.create(report=report, image=photo)

        return Response(
            {
                "report": ProductReportSerializer(report, context={"request": request}).data,
                "integrity": integrity_dict(product),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReportFlagView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, report_id):
        report = get_object_or_404(ProductReport, pk=report_id, is_hidden=False)
        if report.user_id == request.user.id:
            return Response({"detail": "You can't flag your own report."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ReportFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ReportFlag.objects.get_or_create(
            report=report, user=request.user, defaults={"reason": serializer.validated_data.get("reason", "")}
        )
        return Response({"detail": "Thanks -- an admin will review this report."}, status=status.HTTP_201_CREATED)
