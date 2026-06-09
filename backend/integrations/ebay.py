from abc import ABC, abstractmethod


class EbayBrowseAdapter(ABC):
    @abstractmethod
    def search_active(self, query: str, **kw):
        raise NotImplementedError("Implemented in Phase 2")


class EbayInventoryAdapter(ABC):
    @abstractmethod
    def create_or_replace_item(self, sku, payload):
        raise NotImplementedError("Implemented in Phase 4")

    @abstractmethod
    def create_offer(self, payload):
        raise NotImplementedError("Implemented in Phase 4")

    @abstractmethod
    def publish_offer(self, offer_id):
        raise NotImplementedError("Implemented in Phase 4")
