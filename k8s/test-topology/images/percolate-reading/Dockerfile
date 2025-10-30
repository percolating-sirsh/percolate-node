FROM python:3.12-slim

WORKDIR /app

# Install dependencies (including heavy parsing deps)
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.30.6 \
    httpx==0.27.0 \
    nats-py==2.8.0 \
    python-multipart==0.0.12 \
    minio==7.2.5 \
    pypdf==4.0.0 \
    openpyxl==3.1.2 \
    python-docx==1.1.0 \
    pillow==10.2.0 \
    beautifulsoup4==4.12.3

COPY app.py .

CMD ["python", "app.py"]
