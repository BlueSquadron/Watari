# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Stage 2: Production image
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
