from copy import copy, deepcopy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework import serializers

from apps.listing.channel_listings import CHANNEL_LABELS, item_listing_state
from apps.listing.models import ChannelListing, ListingBoilerplate, ListingDraft
from apps.listing.readiness import check_readiness, readiness_summary
from apps.listing.editor import EDITABLE_CHANNEL_FIELDS, LISTING_FIELDS, apply_price_choice, signature, snapshot_signature


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
    editor_save = serializers.BooleanField(write_only=True, required=False)
    expected_updated_at = serializers.DateTimeField(write_only=True, required=False)
    price_choice = serializers.JSONField(write_only=True, required=False)

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
            "editor_save", "expected_updated_at", "price_choice",
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
        if self.instance is not None:
            try:
                self.instance.assert_editable()
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"detail": exc.messages}) from None
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
        if self.instance is not None and status == ListingDraft.Status.READY and not data.get("editor_save"):
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
        editor_save = validated_data.pop("editor_save", False)
        expected = validated_data.pop("expected_updated_at", None)
        choice = validated_data.pop("price_choice", None)
        if editor_save:
            if expected is None:
                raise serializers.ValidationError({"expected_updated_at": "Reload the draft before saving."})
            if "status" in validated_data or "channel" in validated_data:
                raise serializers.ValidationError({"detail": "Editor saves cannot change draft state or channel."})
            # A conditional claim also protects SQLite, where row locks do nothing.
            with transaction.atomic():
                claimed = ListingDraft.objects.filter(pk=instance.pk, updated_at=expected).update(updated_at=timezone.now())
                if not claimed:
                    error = APIException("This draft changed elsewhere. Reload before saving; your text has not been replaced.")
                    error.status_code = 409
                    raise error
                instance.refresh_from_db()
                instance.assert_editable()
                channel = deepcopy(instance.channel_data or {})
                incoming = validated_data.get("channel_data", {})
                if not isinstance(incoming, dict):
                    raise serializers.ValidationError({"channel_data": "Provide a field mapping."})
                specifics = validated_data.get("item_specifics", instance.item_specifics)
                if not isinstance(specifics, list) or any(not isinstance(row, dict) or not isinstance(row.get("name"), str) or not isinstance(row.get("value"), str) for row in specifics):
                    raise serializers.ValidationError({"item_specifics": "Provide name/value text rows."})
                for key in EDITABLE_CHANNEL_FIELDS:
                    if key in incoming:
                        if not isinstance(incoming[key], str) or len(incoming[key]) > 400:
                            raise serializers.ValidationError({"channel_data": f"Invalid {key}."})
                        channel[key] = incoming[key]
                if channel.get("offer_id") and not channel.get("editor_staged_baseline"):
                    channel["editor_staged_baseline"] = {"fields": signature(instance), "snapshot": snapshot_signature(instance)}
                validated_data["channel_data"] = channel
                photos = validated_data.get("photo_ids", instance.photo_ids)
                if not isinstance(photos, list) or len(photos) != len(set(map(str, photos))) or set(map(str, photos)) - set(map(str, instance.item.photos.values_list("id", flat=True))):
                    raise serializers.ValidationError({"photo_ids": "Choose unique photos belonging to this item."})
                try:
                    meta = apply_price_choice(instance, validated_data, choice)
                except DjangoValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict) from None
                origins = deepcopy(meta.get("editor_sources") or {})
                for field in LISTING_FIELDS:
                    if field in validated_data and validated_data[field] != getattr(instance, field):
                        origins[field] = "Human edit in listing editor"
                for key in EDITABLE_CHANNEL_FIELDS:
                    if channel.get(key) != (instance.channel_data or {}).get(key):
                        origins[key] = "Human selection in listing editor"
                meta["editor_sources"] = origins
                if "boilerplate" in validated_data and validated_data["boilerplate"] != instance.boilerplate:
                    origins["boilerplate"] = "Human selection in listing editor"
                validated_data["generated_meta"] = meta
                return self._save_fields(instance, validated_data)
        return self._save_fields(instance, validated_data)

    def _save_fields(self, instance, validated_data):
        if "title" in validated_data and validated_data["title"] != instance.title:
            validated_data["title_edited"] = True
        if (
            "description_html" in validated_data
            and validated_data["description_html"] != instance.description_html
        ):
            validated_data["description_edited"] = True
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"detail": exc.messages}) from None


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
