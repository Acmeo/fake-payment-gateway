FROM python:3.12-slim AS base

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
