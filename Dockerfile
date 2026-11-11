FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
# No cache mount: Railway requires service-specific cache ids.
RUN uv sync --frozen --no-dev --no-install-project --no-cache

FROM python:3.12-slim-bookworm
# libcairo2: runtime library for cairosvg/cairocffi
RUN apt-get update && apt-get install -y --no-install-recommends libcairo2 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# MALLOC_ARENA_MAX=2: stops glibc growing one memory arena per thread.
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    MALLOC_ARENA_MAX=2
COPY --chown=app:app . .
# Build-time key only for collectstatic; the real SECRET_KEY comes from Railway at runtime.
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput
USER app
CMD ["sh", "bin/start.sh"]
