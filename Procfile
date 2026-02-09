# Heroku process types
# Web dyno (FastAPI API). Scale to 0 if you host the API elsewhere.
web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-8000}

# Worker dyno (continuous ingestion scheduler)
worker: python -m app.worker
