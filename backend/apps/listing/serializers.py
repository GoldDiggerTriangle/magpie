from copy import copy

from rest_framework import serializers

from apps.listing.channel_listings import CHANNEL_LABELS, item_listing_state
from apps.listing.models import ChannelListing, ListingBoilerplate, ListingDraft
from apps.listing.readiness import check_readiness, readiness_summary


class ListingBoilerplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingBoilerplate
        fields = [
            "id",
            "channel",
            "name",
            "is_active",
            "body_html",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ListingDraftSerializer(serializers.ModelSerializer):
    readiness_summary = serializers.SerializerMethodField()

    class Meta:
        model = ListingDraft
        fields = [
            "id",
            "item",
            "status",
            "channel",
            "channel_data",
            "title",
            "subtitle",
            "description_html",
            "listing_format",
            "price",
            "currency",
            "quantity",
            "est_shipping_note",
            "item_specifics",
            "photo_ids",
            "include_sku_footer",
            "boilerplate",
            "title_edited",
            "description_edited",
            "generated_meta",
            "exported_at",
            "readiness_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "item",
            "title_edited",
            "description_edited",
            "generated_meta",
            "exported_at",
            "readiness_summary",
            "created_at",
            "updated_at",
        ]

    def get_readiness_summary(self, obj):
        return readiness_summary(obj)

    def validate(self, data):
        quantity = data.get(
            "quantity",
            self.instance.quantity if self.instance else ListingDraft._meta.get_field("quantity").default,
        )
        try:
            quantity_value = int(quantity or 0)
        except (TypeError, ValueError):
            quantity_value = 0
        if quantity_value <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})

        status = data.get("status", self.instance.status if self.instance else ListingDraft.Status.DRAFT)
        if self.instance is not None and status == ListingDraft.Status.READY:
            candidate = copy(self.instance)
            for field, value in data.items():
                setattr(candidate, field, value)
            failures = [
                check.as_dict()
                for check in check_readiness(candidate)
                if check.level == "fail"
            ]
            if failures:
                raise serializers.ValidationError(
                    {"status": "Ready requires zero readiness failures.", "readiness": failures}
                )
        return data

    def update(self, instance, validated_data):
        if "title" in validated_data and validated_data["title"] != instance.title:
            validated_data["title_edited"] = True
        if (
            "description_html" in validated_data
            and validated_data["description_html"] != instance.description_html
        ):
            validated_data["description_edited"] = True
        return super().update(instance, validated_data)


class ChannelListingSerializer(serializers.ModelSerializer):
    active = serializers.BooleanField(read_only=True)
    channel_label = serializers.SerializerMethodField()
    item_sku = serializers.CharField(source="item.sku", read_only=True)
    item_title = serializers.CharField(source="item.title", read_only=True)
    days_listed = serializers.SerializerMethodField()
    take_down_state = serializers.SerializerMethodField()

    class Meta:
        model = ChannelListing
        fields = [
            "id",
            "item",
            "item_sku",
            "item_title",
            "channel",
            "channel_label",
            "listed_at",
            "ended_at",
            "active",
            "days_listed",
            "url",
            "note",
            "source_listing_draft",
            "take_down_state",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "item_sku",
            "item_title",
            "channel_label",
            "active",
            "days_listed",
            "source_listing_draft",
            "take_down_state",
            "created_at",
            "updated_at",
        ]

    def get_channel_label(self, obj):
        return CHANNEL_LABELS.get(obj.channel, obj.get_channel_display())

    def get_days_listed(self, obj):
        end = obj.ended_at or self.context.get("now")
        if end is None:
            from django.utils import timezone

            end = timezone.now()
        return max((end.date() - obj.listed_at.date()).days, 0)

    def get_take_down_state(self, obj):
        item = getattr(obj, "item", None)
        if item is None:
            return None
        state = item_listing_state(item)
        return {
            "state": state["state"],
            "message": state["message"],
            "quantity_sold": state["quantity_sold"],
            "quantity_remaining": state["quantity_remaining"],
            "quantity_total": state["quantity_total"],
        }
