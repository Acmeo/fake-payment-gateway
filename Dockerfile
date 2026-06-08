FROM python:3.12-slim AS base

# Version is injected from outside (release workflow passes the release
# tag as VERSION). Without .git inside the build context, hatch-vcs
# cannot derive a version on its own; we expose VERSION via the
# setuptools-scm override that hatch-vcs honors, so the wheel that
# `uv sync` builds inside the image is stamped with it. Default 0.0.0
# is for local dev builds.
ARG VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir --root-user-action=ignore uv==0.8.22

COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev

COPY src ./src
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uvicorn", "fake_payment_gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
