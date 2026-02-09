import os
from dotenv import load_dotenv

# Load .env as early as possible so downstream modules (e.g., DB) see env vars
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, upload, query
from app.routes import metrics
from app.routes import discovery
from app.routes import earnings
from app.routes import watchlist
from app.routes import admin
from app.routes import market
from app.db.base import init_db

app = FastAPI(title="Earnings AI Backend")

# Default origins: localhost (dev), Vercel subdomains, and production domains (apex + www)
origins_env = os.getenv(
    "ALLOW_ORIGINS",
    "http://localhost:3000,https://*.vercel.app,https://tradeearnings.ai,https://www.tradeearnings.ai",
)
regex_env = os.getenv("ALLOW_ORIGIN_REGEX", "")

# Build allow list and optional regex for wildcard domains (e.g., vercel.app)
raw_origins = [o.strip() for o in origins_env.split(",") if o.strip()] if origins_env else ["*"]
allowed_origins = [o for o in raw_origins if "*" not in o or o == "*"]

allow_origin_regex = regex_env.strip() or None
if not allow_origin_regex:
    # Heuristic: convert common wildcard patterns to regex for popular patterns
    for o in raw_origins:
        if o.startswith("https://*.") and o.endswith("vercel.app"):
            allow_origin_regex = r"^https://.*\\.vercel\\.app$"
            break

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    # Initialize DB if configured (P1)
    init_db()

app.include_router(health.router)
app.include_router(upload.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(earnings.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Earnings AI Backend running"}
