import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()

from apps.ebay.startup import recover_interrupted_publishes
recover_interrupted_publishes()
