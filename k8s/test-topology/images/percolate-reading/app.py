#!/usr/bin/env python3
"""
Percolate Reading Gateway/Worker
- Gateway mode: Receives file uploads, streams to S3, publishes NATS job
- Worker mode: Subscribes to NATS, downloads from S3, processes (dry-run)
"""
import os
import asyncio
import io
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from fastapi.responses import JSONResponse
from minio import Minio
import nats
from nats.js import JetStreamContext
import json
import hashlib
from datetime import datetime

# Configuration
MODE = os.getenv("MODE", "gateway")  # gateway or worker
TIER = os.getenv("TIER", "small")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000").replace("http://", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "percolate")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "percolate-secret")
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
BUCKET_NAME = "percolate-uploads"

app = FastAPI(title="Percolate Reading")

# S3 client (MinIO)
s3_client = None
nats_client = None
js = None

@app.on_event("startup")
async def startup():
    global s3_client, nats_client, js
    s3_client = Minio(
        S3_ENDPOINT,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        secure=False
    )

    # Connect to NATS
    nats_client = await nats.connect(NATS_URL)
    js = nats_client.jetstream()

    # Create bucket if gateway mode
    if MODE == "gateway":
        create_bucket()

    # Start worker if worker mode
    if MODE == "worker":
        print("MODE is worker, starting worker_loop task")
        task = asyncio.create_task(worker_loop())
        task.add_done_callback(lambda t: print(f"Worker task completed: {t.exception() if t.exception() else 'Success'}"))

@app.on_event("shutdown")
async def shutdown():
    if nats_client:
        await nats_client.close()

def create_bucket():
    """Create S3 bucket using MinIO API"""
    try:
        if not s3_client.bucket_exists(BUCKET_NAME):
            s3_client.make_bucket(BUCKET_NAME)
            print(f"Bucket created: {BUCKET_NAME}")
        else:
            print(f"Bucket already exists: {BUCKET_NAME}")
    except Exception as e:
        print(f"Error creating bucket: {e}")

async def stream_to_s3(file: UploadFile, object_key: str) -> dict:
    """Stream file to S3 using MinIO client"""
    chunk_size = 1024 * 1024  # 1MB chunks
    file_hash = hashlib.sha256()
    total_bytes = 0

    # Create a file-like object that streams through the upload
    chunks = []
    while chunk := await file.read(chunk_size):
        file_hash.update(chunk)
        total_bytes += len(chunk)
        chunks.append(chunk)

    # Create BytesIO from chunks for MinIO
    file_data = io.BytesIO(b"".join(chunks))

    # Upload to MinIO
    try:
        s3_client.put_object(
            BUCKET_NAME,
            object_key,
            file_data,
            length=total_bytes,
            content_type=file.content_type or "application/octet-stream"
        )
        print(f"Uploaded {total_bytes} bytes to {object_key}")
    except Exception as e:
        print(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

    return {
        "object_key": object_key,
        "size": total_bytes,
        "sha256": file_hash.hexdigest()
    }

async def publish_job(tenant_id: str, object_key: str, metadata: dict):
    """Publish job to NATS queue based on tier"""
    stream_name = f"jobs-{TIER}"
    subject = f"jobs.{TIER}.parse"

    # Ensure stream exists
    try:
        await js.stream_info(stream_name)
    except:
        await js.add_stream(name=stream_name, subjects=[f"jobs.{TIER}.>"])

    job = {
        "tenant_id": tenant_id,
        "object_key": object_key,
        "tier": TIER,
        "timestamp": datetime.utcnow().isoformat(),
        **metadata
    }

    await js.publish(subject, json.dumps(job).encode())
    print(f"Published job to {subject}: {object_key}")

@app.post("/api/v1/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """Upload file endpoint - streams to S3 and publishes job"""
    if MODE != "gateway":
        raise HTTPException(status_code=400, detail="Not in gateway mode")

    # Generate object key
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    object_key = f"{x_tenant_id}/{timestamp}-{file.filename}"

    # Stream to S3
    s3_result = await stream_to_s3(file, object_key)

    # Publish job to NATS
    await publish_job(x_tenant_id, object_key, {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": s3_result["size"],
        "sha256": s3_result["sha256"]
    })

    return JSONResponse({
        "status": "uploaded",
        "tenant_id": x_tenant_id,
        "object_key": object_key,
        "size": s3_result["size"],
        "sha256": s3_result["sha256"]
    })

@app.get("/health")
async def health():
    return {"status": "healthy", "mode": MODE, "tier": TIER}

async def worker_loop():
    """Worker mode: subscribe to NATS, download file, process (dry-run), shutdown"""
    stream_name = f"jobs-{TIER}"
    subject = f"jobs.{TIER}.>"

    print(f"Worker starting for tier={TIER}, stream={stream_name}")

    # Ensure stream exists
    try:
        info = await js.stream_info(stream_name)
        print(f"Stream {stream_name} found with {info.state.messages} messages")
    except Exception as e:
        print(f"Stream {stream_name} doesn't exist yet: {e}")
        print("Waiting 5s and exiting...")
        await asyncio.sleep(5)
        return

    # Subscribe
    subscription = await js.subscribe(subject, durable=f"worker-{TIER}")

    async for msg in subscription.messages:
        job = json.loads(msg.data.decode())
        print(f"Received job: {job['object_key']}")

        # Download file from S3 (streaming)
        object_key = job["object_key"]

        try:
            response = s3_client.get_object(BUCKET_NAME, object_key)

            # Dry-run: just consume the stream without processing
            total_bytes = 0
            while True:
                chunk = response.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                # In real mode, would pass to parser here

            response.close()
            response.release_conn()
            print(f"Downloaded {total_bytes} bytes from {object_key} (dry-run)")
        except Exception as e:
            print(f"Failed to download {object_key}: {e}")
            await msg.nak()
            continue

        # Acknowledge job
        await msg.ack()
        print(f"Job completed: {object_key}")

        # Dry-run: shutdown after one job
        print("Dry-run complete, shutting down worker")
        break

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
