from rest_framework import serializers

from .models import ProductReport, ReportPhoto

MAX_PHOTOS_PER_REPORT = 4
MAX_PHOTO_BYTES = 5 * 1024 * 1024


class ReportPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportPhoto
        fields = ["id", "image"]


class ProductReportSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    photos = ReportPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = ProductReport
        fields = [
            "id", "username", "verdict", "comment", "where_bought",
            "batch_number", "photos", "created_at",
        ]


class ReportCreateSerializer(serializers.Serializer):
    verdict = serializers.ChoiceField(choices=ProductReport.Verdict.choices)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    where_bought = serializers.CharField(required=False, allow_blank=True, max_length=255)
    batch_number = serializers.CharField(required=False, allow_blank=True, max_length=64)


class ReportFlagSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
