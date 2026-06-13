from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
STATIC_ROOT = BACKEND_DIR / "staticfiles"
SMOKE_TMP = REPO_ROOT / ".tmp"
LAN_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000,http://192.168.1.86:8000"


def fetch(url: str, host: str | None = None) -> tuple[int, str, str]:
    headers = {"Host": host} if host else {}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, response.headers.get("content-type", ""), body


def wait_for_health(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, _, body = fetch(f"{base_url}/api/health/")
            if status == 200 and json.loads(body)["status"] == "ok":
                return
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Waitress health check did not become ready: {last_error}")


def assert_ok_html(url: str, label: str) -> str:
    status, content_type, body = fetch(url)
    if status != 200:
        raise AssertionError(f"{label} returned {status}")
    if "text/html" not in content_type:
        raise AssertionError(f"{label} returned unexpected content type {content_type!r}")
    if 'id="root"' not in body:
        raise AssertionError(f"{label} did not return the SPA index.html")
    return body


def assert_static_asset(base_url: str, html: str) -> None:
    assets = sorted(set(re.findall(r'/(assets/[^"\']+\.(?:js|css))', html)))
    if not assets:
        raise AssertionError("SPA index.html did not reference built JS/CSS assets")
    status, content_type, _ = fetch(f"{base_url}/{assets[0]}")
    if status != 200:
        raise AssertionError(f"Built asset {assets[0]} returned {status}")
    if not any(kind in content_type for kind in ["javascript", "text/css"]):
        raise AssertionError(f"Built asset {assets[0]} returned {content_type!r}")


def assert_admin_served(base_url: str) -> None:
    status, content_type, body = fetch(f"{base_url}/admin/login/")
    if status != 200:
        raise AssertionError(f"admin login returned {status}")
    if "text/html" not in content_type:
        raise AssertionError(f"admin login returned {content_type!r}")
    if "Django administration" not in body:
        raise AssertionError("admin login did not return the Django admin page")


def assert_plain_404(base_url: str) -> None:
    try:
        fetch(f"{base_url}/missing-static-file.txt")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code != 404:
            raise AssertionError(f"missing file returned {exc.code}") from exc
        debug_markers = ["Using the URLconf", "Traceback", "Request Method:"]
        if any(marker in body for marker in debug_markers):
            raise AssertionError("missing file returned a debug error page")
        return
    raise AssertionError("missing file did not return 404")


def assert_no_hardcoded_localhost_api() -> None:
    forbidden = [b"http://localhost:8000", b"http://127.0.0.1:8000"]
    offenders: list[str] = []
    for path in STATIC_ROOT.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if any(marker in data for marker in forbidden):
            offenders.append(str(path.relative_to(STATIC_ROOT)))
    if offenders:
        raise AssertionError(
            "Production frontend build contains hardcoded localhost API URLs: "
            + ", ".join(offenders)
        )


def assert_bad_host_rejected(base_url: str) -> None:
    try:
        fetch(f"{base_url}/api/health/", host="not-allowed.example")
    except HTTPError as exc:
        if exc.code == 400:
            return
        raise AssertionError(f"Unexpected bad Host response: {exc.code}") from exc
    raise AssertionError("Unlisted Host header was not rejected")


def main() -> int:
    if not (STATIC_ROOT / "index.html").exists():
        raise RuntimeError(
            "Collected SPA index is missing. Run frontend build and collectstatic first."
        )

    port = os.getenv("MAGPIE_SMOKE_PORT", "8765")
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    env.setdefault("DEBUG", "0")
    env.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,192.168.1.86")
    env.setdefault("CSRF_TRUSTED_ORIGINS", LAN_ORIGINS)
    env["MAGPIE_HOST"] = "127.0.0.1"
    env["MAGPIE_PORT"] = port

    SMOKE_TMP.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w+",
        delete=False,
        dir=SMOKE_TMP,
        prefix="magpie-smoke-",
        suffix=".log",
    ) as log:
        process = subprocess.Popen(
            [sys.executable, "serve.py"],
            cwd=BACKEND_DIR,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_path = Path(log.name)

    try:
        wait_for_health(base_url)
        root_html = assert_ok_html(f"{base_url}/", "root route")
        assert_ok_html(f"{base_url}/inventory/sprint9-smoke", "deep link route")
        assert_static_asset(base_url, root_html)
        assert_admin_served(base_url)
        assert_plain_404(base_url)
        assert_no_hardcoded_localhost_api()
        assert_bad_host_rejected(base_url)
    except Exception:
        if process.poll() is not None:
            sys.stderr.write(log_path.read_text(encoding="utf-8", errors="replace"))
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        try:
            log_path.unlink(missing_ok=True)
        except PermissionError:
            pass

    print("Production Waitress/WhiteNoise smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
