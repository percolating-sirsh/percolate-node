FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.30.6 \
    prometheus-client==0.20.0 \
    httpx==0.27.0 \
    opentelemetry-api==1.27.0 \
    opentelemetry-sdk==1.27.0 \
    opentelemetry-exporter-otlp==1.27.0 \
    opentelemetry-exporter-prometheus==0.48b0 \
    opentelemetry-instrumentation-fastapi==0.48b0

# Copy application
COPY app.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
