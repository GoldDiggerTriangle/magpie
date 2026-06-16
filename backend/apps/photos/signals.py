from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.photos.models import PhotoAsset, PhotoDerivative
from integrations.storage import LocalFileStorageAdapter


@receiver(pre_delete, sender=PhotoAsset)
def delete_photo_files(sender, instance: PhotoAsset, **kwargs) -> None:
    storage = LocalFileStorageAdapter()
    for key in [instance.original_path, instance.processed_path, instance.thumb_path]:
        if key:
            storage.delete(key)


@receiver(pre_delete, sender=PhotoDerivative)
def delete_photo_derivative_files(sender, instance: PhotoDerivative, **kwargs) -> None:
    storage = LocalFileStorageAdapter()
    for key in [instance.fixed_path, instance.thumb_path]:
        if key:
            storage.delete(key)
