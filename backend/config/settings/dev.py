from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")  # noqa: F405
