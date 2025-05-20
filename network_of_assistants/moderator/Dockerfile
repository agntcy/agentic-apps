FROM python:3.13-bookworm AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project --package moderator --no-install-workspace

# Copy code into builder
COPY . /src
WORKDIR /src

# Install just the pdf_assistant package
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev --no-editable --package moderator

FROM python:3.13.2-bookworm AS runner

# Copy venv from builder with just the dependencies we need + our package
COPY --from=builder --chown=app:app /app /app
COPY ./ads /ads

CMD ["/app/bin/moderator"]
