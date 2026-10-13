# Build/run verification is pending explicit permission to use containers.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /var/lib/orderflow/files \
    && chown -R app:app /var/lib/orderflow

# Fully pinned runtime dependencies; development tools stay outside this image.
COPY requirements.lock ./requirements.lock
RUN pip install --requirement requirements.lock
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
