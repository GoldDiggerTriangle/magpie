from django.urls import resolve


def test_admin_login_url_resolves_to_django_admin_not_spa_fallback():
    match = resolve("/admin/login/")

    assert match.view_name == "admin:login"
    assert match.view_name != "spa-index"


def test_admin_root_route_reaches_django_admin_before_spa_fallback():
    match = resolve("/admin/")

    assert match.view_name == "admin:index"
    assert match.view_name != "spa-index"
