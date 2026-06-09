from abc import ABC, abstractmethod


class MetalsPriceAdapter(ABC):
    @abstractmethod
    def spot_price(self, metal: str, currency: str = "AUD"):
        raise NotImplementedError("Implemented in Phase 2")
