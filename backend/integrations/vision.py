from abc import ABC, abstractmethod


class OcrAdapter(ABC):
    @abstractmethod
    def read_text(self, image_bytes):
        raise NotImplementedError("Implemented in Phase 5")


class VisionAdapter(ABC):
    @abstractmethod
    def classify(self, image_bytes):
        raise NotImplementedError("Implemented in Phase 5")
