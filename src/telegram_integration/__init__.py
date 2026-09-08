def main() -> None:  # pragma: no cover - local dev entrypoint, not exercised by tests
    import uvicorn

    uvicorn.run("telegram_integration.main:app", host="127.0.0.1", port=8000, reload=True)
