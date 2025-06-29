import uuid

import redis
from django.conf import settings
from pymongo import MongoClient
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.taxonomies import VendorType

# --- Database and Queue Connection Functions ---
# These functions will be called when a connection is needed, not at startup.


def get_mongo_collection():
    """Establishes a connection to MongoDB and returns the jobs collection."""
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.vendordb
    return db.jobs


def get_redis_client():
    """Establishes a connection to Redis."""
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


class JobSubmissionView(APIView):
    """
    1. POST /jobs
    Accepts any JSON payload and queues it for processing.
    """

    def post(self, request, *args, **kwargs):
        request_id = str(uuid.uuid4())
        payload = request.data.get("payload", {})
        vendor = (
            VendorType.SYNC
            if request.data.get("vendor", "sync") == "sync"
            else VendorType.ASYNC
        )

        try:
            jobs_collection = get_mongo_collection()
            redis_client = get_redis_client()

            # 1. Create job entry in MongoDB
            job_data = {
                "request_id": request_id,
                "status": "processing",
                "payload": payload,
                "vendor": vendor,
                "result": None,
            }
            jobs_collection.insert_one(job_data)

            # 2. Add job to Redis Stream for the worker
            response_dict = {"request_id": request_id}
            redis_client.xadd(settings.REDIS_STREAM_NAME, response_dict)

            return Response(
                response_dict,
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            # Log the exception and return a server error
            print(f"ERROR in JobSubmissionView: {e}")
            return Response(
                {"error": "Failed to queue job due to a server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class JobStatusView(APIView):
    """
    4. GET /jobs/{request_id}
    Looks up the job and returns its status and result if complete.
    """

    def get(self, request, request_id, *args, **kwargs):
        try:
            jobs_collection = get_mongo_collection()
            job = jobs_collection.find_one(
                {"request_id": request_id},
                {"_id": 0},
            )

            if not job:
                return Response(
                    {"error": "Job not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if job["status"] == "complete":
                return Response(
                    {
                        "request_id": job["request_id"],
                        "status": job["status"],
                        "result": job["result"],
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"request_id": job["request_id"], "status": job["status"]},
                    status=status.HTTP_200_OK,
                )
        except Exception as e:
            print(f"ERROR in JobStatusView: {e}")
            return Response(
                {
                    "error": """Failed to retrieve job
                    status due to a server error.""",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VendorWebhookView(APIView):
    """
    3. POST /vendor-webhook/{vendor}
    The endpoint for asynchronous vendors to push their results to.
    """

    def post(self, request, vendor, *args, **kwargs):
        data = request.data
        request_id = data.get("request_id")

        if not request_id:
            return Response(
                {"error": "request_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            jobs_collection = get_mongo_collection()
            update_result = jobs_collection.update_one(
                {"request_id": request_id},
                {
                    "$set": {
                        "status": "complete",
                        "result": data.get("final_result", {}),
                    }
                },
            )

            if update_result.matched_count == 0:
                # This could also be a timing issue,
                # log it but don't error out loudly
                print(
                    f"WARNING: Webhook for {vendor} received"
                    "for non-existent job {request_id}"
                )
                return Response(
                    {"error": "Job not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            print(f"Webhook for {vendor} completed job {request_id}")
            return Response({"status": "success"}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"ERROR in VendorWebhookView: {e}")
            return Response(
                {"error": "Failed to process webhook due to a server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
