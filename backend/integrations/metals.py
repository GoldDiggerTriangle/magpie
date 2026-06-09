from abc import ABC, abstractmethod


class MetalsPriceAdapter(ABC):
    @abstractmethod
    def spot_price(self, metal: str, currency: str = "AUD"):
        raise NotImplementedError("Live metals pricing is deferred to Sprint 3")
