FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system app && adduser --system --ingroup app app
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=app:app src ./src
USER app
EXPOSE 8000
CMD ["uvicorn", "battle_school_lunch.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
