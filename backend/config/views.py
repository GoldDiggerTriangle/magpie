from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache


@never_cache
def spa_index(request):
    index_path = settings.STATIC_ROOT / "index.html"
    if not index_path.exists():
        index_path = settings.FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise Http404("Frontend build is missing. Run npm run build and collectstatic.")
    return FileResponse(index_path.open("rb"), content_type="text/html")
