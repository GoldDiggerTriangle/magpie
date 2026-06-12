from django.core.exceptions import ImproperlyConfigured, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.ebay import EbayUnavailable
from apps.ebay.serializers import (
    CategoryAspectsQuerySerializer,
    CategorySuggestionsQuerySerializer,
    ConnectCompleteSerializer,
    MerchantLocationCreateSerializer,
    MerchantLocationSerializer,
)
from apps.ebay import aspects
from apps.ebay import services


class EbayConnectStartView(APIView):
    def post(self, request):
        try:
            return Response(services.start_connect(actor=request.user))
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except EbayUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayConnectCompleteView(APIView):
    def post(self, request):
        serializer = ConnectCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            summary = services.complete_connect(
                pasted_url=serializer.validated_data.get("pasted_url"),
                code=serializer.validated_data.get("code"),
                state=serializer.validated_data.get("state"),
                actor=request.user,
            )
        except ValidationError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "environment": summary.environment,
                "ebay_user_id": summary.ebay_user_id,
                "ebay_username": summary.ebay_username,
                "scopes": summary.scopes,
                "access_token_expires_at": summary.access_token_expires_at,
                "refresh_token_expires_at": summary.refresh_token_expires_at,
            }
        )


class EbayDisconnectView(APIView):
    def post(self, request):
        services.disconnect(actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EbayStatusView(APIView):
    def get(self, request):
        return Response(services.status_summary())


class EbayRefreshPoliciesView(APIView):
    def post(self, request):
        try:
            services.refresh_account_snapshot(actor=request.user)
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(services.status_summary())


class EbayCategorySuggestionsView(APIView):
    def get(self, request):
        serializer = CategorySuggestionsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                aspects.suggest_categories(
                    q=serializer.validated_data["q"],
                    actor=request.user,
                )
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayCategoryAspectsView(APIView):
    def get(self, request):
        serializer = CategoryAspectsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                aspects.get_category_aspects(
                    category_id=serializer.validated_data["category_id"],
                    actor=request.user,
                )
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class EbayMerchantLocationView(APIView):
    def get(self, request):
        location = services.current_merchant_location()
        if location is None:
            return Response({"configured": False, "location": None})
        return Response(
            {
                "configured": True,
                "location": MerchantLocationSerializer(location).data,
            }
        )

    def post(self, request):
        serializer = MerchantLocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            location = services.create_merchant_location(
                actor=request.user,
                **serializer.validated_data,
            )
        except (ImproperlyConfigured, EbayUnavailable) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "configured": True,
                "location": MerchantLocationSerializer(location).data,
            },
            status=status.HTTP_201_CREATED,
        )
