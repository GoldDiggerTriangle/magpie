from django.urls import resolve


def test_admin_login_url_resolves_to_django_admin_not_spa_fallback():
    match = resolve("/admin/login/")

    assert match.view_name == "admin:login"
    assert match.view_name != "spa-index"


def test_admin_login_route_is_not_served_by_spa_fallback(client):
    response = client.get("/admin/login/?next=%2F")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "name=\"username\"" in content
    assert "name=\"password\"" in content
    assert "Unexpected Application Error" not in content
    assert "404 Not Found" not in content


def test_admin_root_route_reaches_django_admin_before_spa_fallback(client):
    match = resolve("/admin/")
    assert match.view_name == "admin:index"

    response = client.get("/admin/")

    assert response.status_code in {200, 302}
    if response.status_code == 302:
        assert response["Location"].startswith("/admin/login/")
        return

    content = response.content.decode("utf-8")
    assert "name=\"username\"" in content
    assert "Unexpected Application Error" not in content
