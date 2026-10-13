"""Real Nginx responses; TLS tests additionally run via compose.https.yaml."""

import os
import re
import ssl

import httpx
import pytest

from app.main import create_app

INTEGRATION = pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Requires Nginx")
TLS = pytest.mark.skipif(os.getenv("RUN_TLS") != "1", reason="Requires local TLS overlay")


def assert_headers(response: httpx.Response) -> None:
    csp = response.headers["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "form-action 'self'" in csp
    assert "unsafe-eval" not in csp and "unsafe-inline" not in csp
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers.get("server") == "nginx"


@INTEGRATION
@pytest.mark.parametrize(
    "path,status",
    [
        ("/", 200),
        ("/docs", 200),
        ("/openapi.json", 200),
        ("/api/v1/system", 200),
        ("/api/v1/missing", 404),
        ("/api/v1/auth/me", 401),
        ("/.env", 404),
        ("/.git/config", 404),
    ],
)
def test_nginx_security_headers_http(path: str, status: int) -> None:
    response = httpx.get(os.environ["INTEGRATION_WEB_URL"] + path, timeout=10)
    assert response.status_code == status
    assert_headers(response)
    assert "strict-transport-security" not in response.headers


@INTEGRATION
def test_nginx_rejects_large_auth_body_and_fake_https() -> None:
    web = os.environ["INTEGRATION_WEB_URL"]
    response = httpx.post(
        web + "/api/v1/auth/login",
        content=b"x" * 17000,
        headers={"X-Forwarded-Proto": "https"},
        timeout=10,
    )
    assert response.status_code == 413
    assert_headers(response)
    assert "strict-transport-security" not in response.headers
    response = httpx.post(web + "/api/v1/auth/logout", timeout=10)
    assert response.status_code == 403
    assert_headers(response)


@INTEGRATION
def test_swagger_and_ui_have_only_local_scripts_and_styles() -> None:
    with httpx.Client(base_url=os.environ["INTEGRATION_WEB_URL"], timeout=10) as client:
        for path in ("/", "/docs"):
            page = client.get(path)
            assert "<script>" not in page.text
            assets = re.findall(r'(?:src|href)="([^"#]+)"', page.text)
            assert assets
            for asset in assets:
                assert asset.startswith("/") and not asset.startswith("//"), asset
                assert client.get(asset).status_code == 200


@TLS
@pytest.mark.parametrize(
    "path,status", [("/", 200), ("/api/v1/system", 200), ("/api/missing", 404)]
)
def test_nginx_hsts_over_verified_tls(path: str, status: int) -> None:
    context = ssl.create_default_context(cafile=os.environ["TLS_CA_FILE"])
    response = httpx.get(os.environ["TLS_WEB_URL"] + path, verify=context, timeout=10)
    assert response.status_code == status
    assert_headers(response)
    assert response.headers["strict-transport-security"] == "max-age=31536000"


@TLS
def test_https_redirect_csrf_and_secure_cookie() -> None:
    context = ssl.create_default_context(cafile=os.environ["TLS_CA_FILE"])
    with httpx.Client(base_url=os.environ["TLS_WEB_URL"], verify=context, timeout=10) as client:
        redirect = client.get("http://frontend/api/v1/system", headers={"Host": "evil.example"})
        assert redirect.status_code == 308
        assert redirect.headers["location"] == "https://localhost:8443/api/v1/system"
        csrf = client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200
        assert "Secure" in csrf.headers["set-cookie"] and "HttpOnly" in csrf.headers["set-cookie"]
        assert csrf.headers["cache-control"] == "no-store"
        result = client.post(
            "/api/v1/auth/logout",
            headers={
                "Origin": "https://localhost:8443",
                "X-CSRF-Token": csrf.json()["csrf_token"],
            },
        )
        assert result.status_code == 204


@pytest.mark.parametrize("price", ["0", "-0.01", "-1"])
def test_catalog_rejects_non_positive_price(price: str) -> None:
    schema = create_app().openapi()
    assert not any(
        "price" in model.get("properties", {})
        for model in schema.get("components", {}).get("schemas", {}).values()
    ), "Catalog is now present: replace this explicit skip with POST/PATCH and DB tests"
    pytest.skip(f"M03a not implemented: no product/price API to submit price={price}")
