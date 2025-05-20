FROM python:3.13-bookworm AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.6.13 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=auth.netrc,target=/root/.netrc \
    uv sync --frozen --no-dev --no-install-project --package pdf_assistant --no-install-workspace

# Copy code into builder
COPY . /src
COPY ./pdf_assistant/nexus /nexus
COPY ./pdf_assistant/catalyst /catalyst
WORKDIR /src

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev --no-editable --package pdf_assistant

FROM python:3.13.2-bookworm AS runner

RUN groupadd -r app && useradd -r -g app app && \
    mkdir -p /src /nexus /catalyst && \
    chown -R app:app /src

COPY --from=builder --chown=app:app /app /app
COPY --from=builder --chown=app:app /nexus /nexus
COPY --from=builder --chown=app:app /catalyst /catalyst

USER app
WORKDIR /src

CMD ["/app/bin/pdf-assistant"]
