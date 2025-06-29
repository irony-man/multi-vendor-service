import os
import signal
import time

import httpx
import redis
from pymongo import MongoClient

# --- Graceful Shutdown & Worker Config ---
shutdown_flag = False


def signal_handler(sig, frame):
    global shutdown_flag
    print("Shutdown signal received, will stop after current job...")
    shutdown_flag = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

MOCK_VENDOR_BASE_URL = "http://mock_vendors:8000"

# --- Rate Limiter, Data Cleaner, and Process Job functions ---
RATE_LIMITS = {
    "SYNC": {"tokens": 1, "refill_time": 2},
    "ASYNC": {"tokens": 1, "refill_time": 1},
}


def acquire_token(redis_client, vendor: str):
    """Blocks until a token is available for the given vendor."""
    limit = RATE_LIMITS.get(vendor)
    if not limit:
        return True
    key = f"rate-limit:{vendor}"
    while not shutdown_flag:
        if redis_client.set(key, "1", nx=True, ex=limit["refill_time"]):
            return True
        time.sleep(0.1)
    return False


def data_cleaner(data: dict) -> dict:
    """
    Recursively traverses the dict and strips whitespace
    from all string values.
    """
    if isinstance(data, dict):
        # If it's a dictionary, recurse on each value
        return {k: data_cleaner(v) for k, v in data.items()}
    elif isinstance(data, list):
        # If it's a list, recurse on each item
        return [data_cleaner(item) for item in data]
    elif isinstance(data, str):
        return data.strip()
    else:
        return data

def process_job(jobs_collection, redis_client, request_id: str):
    """The core logic for processing a single job."""
    print(f"Processing job: {request_id}")
    job = jobs_collection.find_one({"request_id": request_id})
    if not job or job.get("status") != "processing":
        print(
            f"""Job {request_id} not found or
              not in 'processing' state. Skipping."""
        )
        return

    jobs_collection.update_one(
        {"request_id": request_id}, {"$set": {"status": "processing"}}
    )
    vendor = job["vendor"]
    vendor_endpoint = "sync-vendor" if vendor == "SYNC" else "async-vendor"
    vendor_url = f"{MOCK_VENDOR_BASE_URL}/{vendor_endpoint}"

    try:
        if not acquire_token(redis_client, vendor):
            print("Shutdown initiated, will not process job.")
            jobs_collection.update_one(
                {"request_id": request_id}, {"$set": {"status": "processing"}}
            )
            return

        payload_to_send = {
            "request_id": request_id,
            "data": data_cleaner(job["payload"]),
        }
        response = httpx.post(vendor_url, json=payload_to_send, timeout=15)
        response.raise_for_status()
        vendor_response = response.json()

        if vendor == "SYNC":
            jobs_collection.update_one(
                {"request_id": request_id},
                {
                    "$set": {
                        "status": "complete",
                        "result": vendor_response.get("result", {}),
                    }
                },
            )
            print(f"Job {request_id} (sync) completed successfully.")
        elif vendor == "ASYNC":
            print(f"Job {request_id} (async) successfully sent to vendor.")

    except httpx.RequestError as e:
        print(f"CRITICAL ERROR calling vendor for job {request_id}: {e}")
        jobs_collection.update_one(
            {"request_id": request_id},
            {"$set": {"status": "failed", "result": {"error": str(e)}}},
        )


# --- Main Function ---
def main():
    """Main worker loop."""
    print("Worker starting up... Docker Compose will wait for dependencies.")

    mongo_client = MongoClient(os.getenv("MONGO_URI"))
    db = mongo_client.vendordb
    jobs_collection = db.jobs
    redis_client = redis.Redis.from_url(
        os.getenv("REDIS_URL"),
        decode_responses=True,
    )

    REDIS_STREAM_NAME = os.getenv("REDIS_STREAM_NAME", "job_stream")
    CONSUMER_GROUP_NAME = "processing_group"
    CONSUMER_NAME = f"consumer-{os.getpid()}"

    try:
        redis_client.xgroup_create(
            REDIS_STREAM_NAME, CONSUMER_GROUP_NAME, id="0", mkstream=True
        )
        print(
            f"""Consumer group '{CONSUMER_GROUP_NAME}'
            created or already exists."""
        )
    except redis.exceptions.ResponseError as e:
        if "name already exists" in str(e):
            print(f"Consumer group '{CONSUMER_GROUP_NAME}' already exists.")
        else:
            raise

    print(f"Worker ({CONSUMER_NAME}) is ready and waiting for jobs...")
    while not shutdown_flag:
        try:
            response = redis_client.xreadgroup(
                CONSUMER_GROUP_NAME,
                CONSUMER_NAME,
                {REDIS_STREAM_NAME: ">"},
                count=1,
                block=2000,
            )
            if not response:
                continue

            message_id, data = response[0][1][0]
            try:
                process_job(jobs_collection, redis_client, data["request_id"])
                redis_client.xack(
                    REDIS_STREAM_NAME,
                    CONSUMER_GROUP_NAME,
                    message_id,
                )
            except Exception as e:
                print(
                    f"""CRITICAL: Unhandled exception during job
                    processing for {data.get('request_id')}: {e}"""
                )
                redis_client.xack(
                    REDIS_STREAM_NAME,
                    CONSUMER_GROUP_NAME,
                    message_id,
                )

        except Exception as e:
            print(f"An error occurred in the main loop: {e}")
            if isinstance(e, redis.exceptions.ConnectionError):
                print("Redis connection lost. Shutting down.")
                break
            time.sleep(5)

    print("Worker shutting down gracefully.")


if __name__ == "__main__":
    main()
