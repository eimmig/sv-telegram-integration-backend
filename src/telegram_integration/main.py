from fastapi import FastAPI

app = FastAPI(title="telegram-integration")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
