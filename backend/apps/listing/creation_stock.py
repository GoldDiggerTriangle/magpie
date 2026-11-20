from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.db.models import F

from apps.inventory.models import InventoryItem


class DraftStockError(ValidationError):
    def payload(self):
        return {"code": self.code, "detail": self.message}


class SoldOut(DraftStockError):
    def __init__(self):
        super().__init__("Sold out \N{EM DASH} nothing to list.", code="sold_out")


class StockChanged(DraftStockError):
    def __init__(self):
        super().__init__("Stock changed. Reload before creating a draft.", code="stock_changed")


def require_remaining_stock(item):
    if item.quantity_remaining <= 0:
        raise SoldOut()


@contextmanager
def claim_creation_stock(item_id, using="default"):
    try:
        with transaction.atomic(using=using):
            item = InventoryItem.objects.using(using).get(pk=item_id)
            revision = item.stock_revision
            # A conditional no-op write takes the sale/quantity writer fence without inventing a stock movement.
            claimed = InventoryItem.objects.using(using).filter(pk=item_id, stock_revision=revision).update(
                stock_revision=F("stock_revision"),
            )
            if claimed != 1:
                raise StockChanged()
            item.refresh_from_db(using=using)
            require_remaining_stock(item)
            yield item
    except OperationalError:
        raise StockChanged() from None
