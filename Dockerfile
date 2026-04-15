FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS builder

RUN pip install --upgrade pip
COPY pyproject.toml .
RUN pip install . --no-deps --target=/install

FROM base AS runtime

COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY src/ /app/src/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

EXPOSE 8000

CMD ["uvicorn", "theseus.main:app", "--host", "0.0.0.0", "--port", "8000"]
