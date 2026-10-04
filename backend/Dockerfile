FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HWA_DATA_DIR=/app/state/data \
    HWA_ARTIFACT_DIR=/app/state/artifacts \
    LLM_CACHE_DIR=/app/state/llm-cache

# libgomp is needed by XGBoost
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
# Seed on first start (data, database, models), then serve the API.
CMD ["sh", "-c", "python seed_data.py --if-empty && uvicorn main:app --host 0.0.0.0 --port 8000"]
