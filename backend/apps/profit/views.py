from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import InventoryItem
from apps.profit.models import ProfitSetting, current_profit_setting
from apps.profit.serializers import ProfitSettingSerializer
from apps.profit.services import (
    PriceBasis,
    buyer_protection_fee,
    buyer_visible_total,
    calculate_buy,
    evidence_options_for_item,
    fees_for_seller_receives,
    median_known_seller_receives,
    seller_price_from_buyer_visible,
)


class ProfitSettingView(APIView):
    def get(self, request):
        return Response(ProfitSettingSerializer(current_profit_setting()).data)

    def put(self, request):
        current = ProfitSetting.objects.order_by("-updated_at").first()
        serializer = ProfitSettingSerializer(current, data=request.data)
        serializer.is_valid(raise_exception=True)
        preference = serializer.save()
        return Response(ProfitSettingSerializer(preference).data)


class EbayFeePreviewView(APIView):
    def get(self, request):
        setting = current_profit_setting()
        seller_price = Decimal(str(request.query_params.get("seller_price", "0") or "0"))
        buyer_total = Decimal(str(request.query_params.get("buyer_total", "0") or "0"))
        fee = fees_for_seller_receives(
            seller_receives=seller_price,
            seller_mode=request.query_params.get("seller_mode") or setting.seller_mode,
            setting=setting,
        )
        return Response(
            {
                "seller_price": str(fee.seller_receives),
                "buyer_visible_total": str(fee.buyer_visible_total),
                "buyer_protection_fee": str(fee.buyer_protection_fee),
                "seller_from_buyer_visible": str(seller_price_from_buyer_visible(buyer_total)) if buyer_total else None,
                "direct_buyer_total": str(buyer_visible_total(seller_price)),
                "direct_bpf": str(buyer_protection_fee(seller_price)),
                "seller_fees": str(fee.total_seller_fees),
                "basis_note": fee.basis_note,
            }
        )


class BuyCalculatorEvidenceView(APIView):
    def get(self, request):
        setting = current_profit_setting()
        item_id = request.query_params.get("item")
        item = get_object_or_404(InventoryItem.objects.select_related("category"), pk=item_id) if item_id else None
        options = evidence_options_for_item(item) if item else []
        suggested = median_known_seller_receives(options)
        return Response(
            {
                "settings": ProfitSettingSerializer(setting).data,
                "item": str(item.id) if item else None,
                "evidence": options,
                "suggested": suggested,
                "empty": item is not None and suggested is None,
                "price_basis_options": [
                    {"id": PriceBasis.SELLER_RECEIVES, "label": "Seller receives"},
                    {"id": PriceBasis.BUYER_VISIBLE, "label": "Buyer-visible total"},
                    {"id": PriceBasis.UNKNOWN, "label": "Unknown - review only"},
                ],
            }
        )


class BuyCalculatorCalculateView(APIView):
    def post(self, request):
        setting = current_profit_setting()
        payload = request.data
        try:
            result = calculate_buy(
                expected_sell_price=payload.get("expected_sell_price"),
                price_basis=payload.get("price_basis") or PriceBasis.SELLER_RECEIVES,
                seller_mode=payload.get("seller_mode") or setting.seller_mode,
                setting=setting,
                target_type=payload.get("target_type") or "roi",
                flat_profit_target=payload.get("flat_profit_target") or setting.default_flat_profit_target,
                roi_pct=payload.get("roi_pct") or setting.default_roi_pct,
                roi_basis=payload.get("roi_basis") or setting.default_roi_basis,
                postage=payload.get("postage") or "0",
                packaging=payload.get("packaging") or "0",
                refurb=payload.get("refurb") or "0",
                asking_price=payload.get("asking_price"),
                evidence_source=payload.get("evidence_source") or "what_if",
                confidence_label=payload.get("confidence_label") or "what-if (your estimate)",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "max_buy": str(result.max_buy),
                "headline": "Max Bid" if payload.get("auction_mode") else "Max Buy Price",
                "verdict": result.verdict,
                "expected_profit_at_asking": str(result.expected_profit_at_asking) if result.expected_profit_at_asking is not None else None,
                "roi_at_asking": str(result.roi_at_asking) if result.roi_at_asking is not None else None,
                "net_proceeds_before_buy": str(result.net_proceeds_before_buy),
                "seller_fees": str(result.seller_fees),
                "non_buy_costs": str(result.non_buy_costs),
                "evidence_source": result.evidence_source,
                "confidence_label": result.confidence_label,
                "roi_basis": result.roi_basis,
            }
        )
