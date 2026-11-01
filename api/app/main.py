from fastapi import FastAPI

from app.routers import auth, items

app = FastAPI(title="MyStash API")
app.include_router(auth.router)
app.include_router(items.router)


@app.get("/health")
def health():
    return {"status": "ok"}
