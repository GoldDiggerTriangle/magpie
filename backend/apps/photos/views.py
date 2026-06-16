from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.photos.fixup import PhotoFixupService
from apps.photos.models import PhotoAsset, PhotoDerivative
from apps.photos.serializers import PhotoAssetSerializer


class PhotoAssetViewSet(ModelViewSet):
    queryset = (
        PhotoAsset.objects.select_related("item", "active_derivative")
        .prefetch_related("derivatives")
        .all()
    )
    serializer_class = PhotoAssetSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = self.get_object()
            if serializer.validated_data.get("is_main") is True:
                PhotoAsset.objects.filter(item=instance.item, is_main=True).exclude(
                    pk=instance.pk
                ).update(is_main=False)
            serializer.save()

    @action(detail=True, methods=["post"], url_path="fixup")
    def generate_fixup(self, request, pk=None):
        photo = self.get_object()
        try:
            PhotoFixupService().generate(photo, request.data.get("parameters") or {})
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return self._photo_response(photo.pk, status_code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="fixup/approve")
    def approve_fixup(self, request, pk=None):
        photo = self.get_object()
        derivative = self._get_derivative(photo, request)
        if derivative is None:
            return Response(
                {"detail": "No pending photo fix-up is available to approve."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        approved = PhotoFixupService().approve(derivative)
        return self._photo_response(approved.pk)

    @action(detail=True, methods=["post"], url_path="fixup/reject")
    def reject_fixup(self, request, pk=None):
        photo = self.get_object()
        derivative = self._get_derivative(photo, request)
        if derivative is None:
            return Response(
                {"detail": "No pending photo fix-up is available to reject."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rejected = PhotoFixupService().reject(derivative)
        return self._photo_response(rejected.pk)

    @action(detail=True, methods=["post"], url_path="fixup/tweak")
    def tweak_fixup(self, request, pk=None):
        photo = self.get_object()
        derivative = self._get_derivative(photo, request)
        if derivative is None:
            return Response(
                {"detail": "No pending photo fix-up is available to tweak."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        PhotoFixupService().tweak(derivative, request.data.get("parameters") or {})
        return self._photo_response(photo.pk, status_code=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="fixup/revert")
    def revert_fixup(self, request, pk=None):
        photo = self.get_object()
        reverted = PhotoFixupService().revert(photo)
        return self._photo_response(reverted.pk)

    def _get_derivative(self, photo: PhotoAsset, request):
        derivative_id = request.data.get("derivative_id")
        queryset = photo.derivatives.filter(status=PhotoDerivative.Status.PENDING_REVIEW)
        if derivative_id:
            return queryset.filter(pk=derivative_id).first()
        return queryset.order_by("-created_at").first()

    def _photo_response(self, pk, *, status_code=status.HTTP_200_OK):
        photo = self.get_queryset().get(pk=pk)
        return Response(
            self.get_serializer(photo).data,
            status=status_code,
        )
