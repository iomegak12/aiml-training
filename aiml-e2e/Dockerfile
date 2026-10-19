# Northwind Finance - loan offer API (educational demo on synthetic data;
# never use for real credit decisions).
#
# Build:  make docker-build      (passes MODEL_VERSION = latest saved model)
# Run:    docker run -p 8000:8000 --env-file .env iomega/northwind-loans-api:0.1.0
#         --env-file provides MODEL_SIGNING_KEY; it is never baked into the image.

# ---------------------------------------------------------------------------
# Stage 1: builder - install the package and its runtime dependencies with uv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
RUN uv venv /opt/venv --python /usr/local/bin/python

COPY pyproject.toml README.md ./
COPY src ./src
# Non-editable install, runtime dependencies only (no dev extras: pytest, httpx)
RUN uv pip install --python /opt/venv/bin/python --no-cache .

# ---------------------------------------------------------------------------
# Stage 2: runtime - slim image with the venv and ONE model version
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ARG MODEL_VERSION
LABEL org.opencontainers.image.title="northwind-loans-api" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.description="Northwind loan offer API - educational demo, synthetic data"

# PROJECT_ROOT: config.py would otherwise resolve paths inside site-packages
ENV PATH=/opt/venv/bin:$PATH \
    PROJECT_ROOT=/app \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY models/loan_offer_model_v${MODEL_VERSION}.pkl models/loan_offer_model_v${MODEL_VERSION}.json ./models/
RUN mkdir -p /app/logs && chown -R app:app /app

USER app
EXPOSE 8000
CMD ["python", "-m", "northwind_loans.api"]
