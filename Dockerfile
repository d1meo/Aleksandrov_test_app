FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -Ls https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
