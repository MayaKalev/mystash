import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://mystash:mystash@localhost:5432/mystash"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Used to sign login tokens. Must be set; there is no default on purpose.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRE_DAYS = 7

# Website addresses allowed to call the API, separated by commas.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# The OpenAI library reads OPENAI_API_KEY from the environment by itself.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
