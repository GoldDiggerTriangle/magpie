from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from .fee_engine import (registry, serialize_version, latest_version, create_version,
                         evaluate_order, adjust_fee)
from .fee_models import FeeScheduleVersion, SaleFeeSnapshot
from .models import FeeSchedule


class FeeCalendarView(APIView):
    def get(self, request):
        current = latest_version()
        return Response({"current": serialize_version(current), "today": str(timezone.localdate()),
            "gst_treatment": "inclusive", "gst_note": "Regan is not registered for GST. Enter GST-inclusive fees exactly as eBay shows them.",
            "categories": registry(), "versions": [serialize_version(v) for v in FeeScheduleVersion.objects.all()],
            "legacy": [{"id": str(f.pk), "name": f.name, "label": "Legacy / unverified - history only"} for f in FeeSchedule.objects.all()],
            "state": "configured" if current and current.periods.exists() else "schedule unknown"})

    def post(self, request):
        try:
            version = create_version(request.data, request.user)
            return Response(serialize_version(version), status=201)
        except (ValueError, ValidationError, KeyError, TypeError):
            # Safe, bounded local validation text only; never echo submitted payloads.
            return Response({"detail": "Check dates (no overlap), required rates, source and the reviewed calendar version."}, status=400)


class FeeCalculateView(APIView):
    def post(self, request):
        try:
            result, _, _ = evaluate_order(request.data)
            return Response(result)
        except (ValueError, ValidationError, KeyError, TypeError):
            return Response({"detail": "Check the complete order inputs, category, delivery country and monetary fields."}, status=400)


class FeeAdjustmentView(APIView):
    def post(self, request, sale_id):
        snapshot = get_object_or_404(SaleFeeSnapshot, sale_id=sale_id)
        try:
            return Response(adjust_fee(snapshot, request.data, request.user), status=201)
        except (ValueError, ValidationError):
            return Response({"detail": "A fee correction requires known fees, explicit signed amount, source and reason."}, status=400)
