FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY tests ./tests
COPY pytest.ini .

RUN useradd -m appuser && mkdir -p /app/storage/bdns && chown -R appuser:appuser /app/storage
USER appuser

EXPOSE 8000
# Hosting platforms inject PORT; locally it falls back to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
