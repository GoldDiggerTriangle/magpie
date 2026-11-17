from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ebay.adapters import effective_environment
from apps.ebay.diagnostics import public_diagnostic, safe_exception
from apps.ebay.models import EbayListingAllocation
from apps.ebay.quantity import check_quantity, item_quantity_state, update_quantity
from apps.ebay.workflow_errors import WorkflowError
from apps.inventory.models import InventoryItem


class ItemEbayQuantityView(APIView):
    def get(self, request, item_id):
        return Response(item_quantity_state(get_object_or_404(InventoryItem, pk=item_id), effective_environment()))


class EbayQuantityActionView(APIView):
    def post(self, request, allocation_id, action):
        allocation = get_object_or_404(EbayListingAllocation.objects.select_related("item", "channel_listing"),
            pk=allocation_id, environment=effective_environment(), closed_at__isnull=True)
        try:
            if action == "check":
                result = check_quantity(allocation, actor=request.user)
            elif action == "update":
                allowed = {"quantity", "stock_revision", "stock_fingerprint", "allocation_revision"}
                if set(request.data) - allowed:
                    raise WorkflowError("quantity_only", "Only reviewed quantity inputs are accepted.", status=400)
                result = update_quantity(allocation, request.data, actor=request.user)
            else:
                return Response(status=404)
        except WorkflowError as exc:
            return Response(exc.payload(), status=exc.status)
        except Exception as exc:
            return Response({"detail": "Quantity check was not confirmed. No retry permission is granted.",
                "diagnostic": public_diagnostic(safe_exception(exc, "inventory.quantity"))}, status=503)
        return Response(result)
