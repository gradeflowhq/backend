FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml .
COPY gradeflow_backend/ gradeflow_backend/

# git is needed only to install gradeflow-engine from GitHub; purge it after
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && pip install --upgrade pip && pip install ".[mysql]" \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

COPY alembic.ini .
COPY migrations/ migrations/
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
