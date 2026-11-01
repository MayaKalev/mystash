from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="MyStash API", version="0.1.0")
app.include_router(auth.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
