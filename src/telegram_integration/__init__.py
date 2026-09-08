def main() -> None:  # pragma: no cover - local dev entrypoint, not exercised by tests
    import uvicorn

    uvicorn.run("telegram_integration.main:app", host="0.0.0.0", port=8000, reload=True)
