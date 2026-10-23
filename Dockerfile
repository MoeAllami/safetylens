# SafetyLens web app (build only: the image is built in CI and never pushed).
# Data is not baked in: build it on the host with `make data-dev`, then mount it:
#   docker build -t safetylens .
#   docker run --rm -p 8000:8000 --env-file .env -v "$PWD/data:/app/data" safetylens
# On linux, pyproject.toml points torch at the CPU wheel index, so the image needs no GPU.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so editing source code does not reinstall torch.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home app && mkdir -p /app/data && chown app /app/data
USER app
ENV PATH="/app/.venv/bin:$PATH" \
    SAFETYLENS_DATA_DIR=/app/data
# The fts extension is installed at build time (the app only loads it, never downloads it).
RUN python -c "import duckdb; duckdb.install_extension('fts')"

EXPOSE 8000
CMD ["safetylens", "serve", "--host", "0.0.0.0", "--port", "8000"]
