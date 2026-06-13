from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    f"{LAN_ORIGINS},{DEV_ORIGINS}",  # noqa: F405
)
