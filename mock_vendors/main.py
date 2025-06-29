import asyncio
import os

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# URL for the main API's webhook, injected via environment variable
API_WEBHOOK_URL = os.getenv("API_WEBHOOK_URL")


class JobPayload(BaseModel):
    request_id: str
    data: dict


@app.post("/sync-vendor")
async def sync_vendor_endpoint(job: JobPayload):
    """Simulates a synchronous vendor that takes 1 second to process."""
    await asyncio.sleep(1)
    return {
        "status": "completed",
        "vendor": "sync",
        "result": {
            "message": "Synchronous processing complete.",
            "original_data": job.data,
        },
    }


@app.post("/async-vendor")
async def async_vendor_endpoint(job: JobPayload):
    """
    Simulates an asynchronous vendor.
    It immediately returns 'accepted' and then
    calls back the webhook after a delay.
    """
    # Run the callback in the background
    asyncio.create_task(send_webhook_callback(job.request_id, job.data))
    return {"status": "accepted"}


async def send_webhook_callback(
    request_id: str,
    original_data: dict,
):
    """Waits for 3 seconds, then posts the final
    result to the main app's webhook."""
    await asyncio.sleep(15)
    final_data = {
        "request_id": request_id,
        "final_result": {
            "message": "Asynchronous processing complete.",
            "original_data": original_data,
        },
    }
    async with httpx.AsyncClient() as client:
        try:
            print(
                f"""Async Vendor: Sending webhook for {request_id}
                to {API_WEBHOOK_URL}"""
            )
            await client.post(API_WEBHOOK_URL, json=final_data, timeout=10)
        except Exception as e:
            print(
                f"""Async Vendor: Failed to send
                  webhook for {request_id}. Error: {e}"""
            )
