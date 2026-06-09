from django.db import transaction

from apps.core.models import SkuSequence


def generate_sku(prefix: str) -> str:
    prefix = (prefix or "GSP").upper()
    with transaction.atomic():
        seq = SkuSequence.objects.select_for_update().filter(prefix=prefix).first()
        if seq is None:
            seq = SkuSequence.objects.create(prefix=prefix, last_value=0)
            seq = SkuSequence.objects.select_for_update().get(pk=seq.pk)
        seq.last_value += 1
        seq.save(update_fields=["last_value"])
    return f"{prefix}-{seq.last_value:05d}"
