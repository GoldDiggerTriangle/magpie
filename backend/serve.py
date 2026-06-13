from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")


def main() -> None:
    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    app = get_wsgi_application()
    serve(
        app,
        host=os.getenv("MAGPIE_HOST", "0.0.0.0"),
        port=int(os.getenv("MAGPIE_PORT", "8000")),
        threads=int(os.getenv("MAGPIE_THREADS", "4")),
    )


if __name__ == "__main__":
    main()
