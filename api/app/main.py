from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import auth, items, tags

app = FastAPI(title="MyStash API")

# The website runs on a different address than the API, so the browser only lets it
# call the API if the API says that address is allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(items.router)
app.include_router(tags.router)


@app.get("/health")
def health():
    return {"status": "ok"}
