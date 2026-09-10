from fastapi.testclient import TestClient

from telegram_integration.main import app

# /health has no auth (Kubernetes probes hit it) - the header is harmless here, kept only for
# consistency with the other test modules that do need it.
client = TestClient(app, headers={"X-Service-Key": "test-service-key"})


def test_health_returns_200_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
