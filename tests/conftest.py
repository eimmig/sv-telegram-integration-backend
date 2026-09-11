import os

# Set before any test module imports telegram_integration.main - the app reads SERVICE_KEY
# lazily via os.environ.get for both its own require_service_key dependency and the outbound
# X-Service-Key it sends to api-gateway. Every TestClient in this suite sends this same literal
# value as its own X-Service-Key header (see TEST_SERVICE_KEY constant below) so existing tests
# don't need to know auth exists.
TEST_SERVICE_KEY = "test-service-key"
os.environ.setdefault("SERVICE_KEY", TEST_SERVICE_KEY)
