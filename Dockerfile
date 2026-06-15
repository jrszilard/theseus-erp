FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS builder

RUN pip install --upgrade pip
# Copy the full package source so hatchling can build the wheel WITH dependencies.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install . --target=/install

FROM base AS runtime

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY alembic/ /app/alembic/
COPY alembic.ini /app/
# These three were missing — the app needs them at runtime:
COPY hull-ui/ /app/hull-ui/
COPY planks/ /app/planks/
COPY blueprints/ /app/blueprints/
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "theseus.main:app", "--host", "0.0.0.0", "--port", "8000"]
