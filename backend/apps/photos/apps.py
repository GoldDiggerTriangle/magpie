from django.apps import AppConfig


class PhotosConfig(AppConfig):
    name = "apps.photos"

    def ready(self) -> None:
        import apps.photos.signals  # noqa: F401
