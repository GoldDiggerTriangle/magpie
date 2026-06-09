from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY == "django-insecure-sprint-0-local-only":  # noqa: F405
    raise ImproperlyConfigured("Set SECRET_KEY in production.")
