import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()

from apps.ebay.startup import recover_interrupted_publishes
recover_interrupted_publishes()
