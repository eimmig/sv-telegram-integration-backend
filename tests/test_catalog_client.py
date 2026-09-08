import httpx
import pytest

from telegram_integration.catalog_client import CatalogEntry, fetch_catalog


def _page(content: list[dict[str, str]], page: int, total_pages: int) -> dict[str, object]:
    return {
        "content": content,
        "page": page,
        "size": 100,
        "totalElements": sum(1 for _ in content) if total_pages == 1 else 150,
        "totalPages": total_pages,
    }


def test_fetches_single_page_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/sports"
        assert request.headers["X-Service-Key"] == "test-key"
        assert request.headers["X-Telegram-User-Id"] == "999"
        assert request.headers["X-Correlation-Id"] == "corr-1"
        assert request.url.params["page"] == "0"
        assert request.url.params["size"] == "100"
        return httpx.Response(200, json=_page([{"id": "s1", "name": "Football"}], page=0, total_pages=1))

    monkeypatch.setenv("SERVICE_KEY", "test-key")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", client.get)

    entries = fetch_catalog("sports", "999", correlation_id="corr-1")

    assert entries == [CatalogEntry(id="s1", name="Football")]


def test_pages_until_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        0: _page([{"id": str(i), "name": f"League {i}"} for i in range(100)], page=0, total_pages=2),
        1: _page([{"id": "100", "name": "League 100"}], page=1, total_pages=2),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requested_page = int(request.url.params["page"])
        return httpx.Response(200, json=pages[requested_page])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", client.get)

    entries = fetch_catalog("leagues", "999", correlation_id="corr-1")

    assert entries is not None
    assert len(entries) == 101
    assert entries[-1] == CatalogEntry(id="100", name="League 100")


def test_returns_empty_list_for_empty_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([], page=0, total_pages=1))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", client.get)

    entries = fetch_catalog("markets", "999", correlation_id="corr-1")

    assert entries == []


def test_returns_none_when_gateway_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_connect_error(*_args: object, **_kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", raise_connect_error)

    entries = fetch_catalog("betting-houses", "999", correlation_id="corr-1")

    assert entries is None


def test_returns_none_on_unexpected_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"title": "invalid-service-key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", client.get)

    entries = fetch_catalog("sports", "999", correlation_id="corr-1")

    assert entries is None


def test_uses_api_gateway_url_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_URL", "http://custom-gateway:9000")
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url).split("?")[0])
        return httpx.Response(200, json=_page([], page=0, total_pages=1))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("telegram_integration.catalog_client.httpx.get", client.get)

    fetch_catalog("sports", "999", correlation_id="corr-1")

    assert captured_urls == ["http://custom-gateway:9000/api/v1/sports"]
