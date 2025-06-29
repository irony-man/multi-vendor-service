# This script checks the availability of MongoDB and Redis.

import os
import sys
import time

import redis
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Number of retries
retries = 10
wait_time = 3  # seconds

for i in range(retries):
    try:
        print("Attempting to connect to services...")

        # --- Check MongoDB ---
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            print("MONGO_URI environment variable not set.")
            sys.exit(1)

        mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        mongo_client.admin.command("ismaster")
        print("MongoDB connection successful.")

        # --- Check Redis ---
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("REDIS_URL environment variable not set.")
            sys.exit(1)

        redis_client = redis.Redis.from_url(redis_url)
        redis_client.ping()
        print("Redis connection successful.")

        # If both checks pass, exit with success code
        sys.exit(0)

    except ConnectionFailure as e:
        print(f"MongoDB connection failed: {e}")
    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print(f"Retrying in {wait_time} seconds... ({i + 1}/{retries})")
    time.sleep(wait_time)

# If the loop completes without a successful connection, exit with failure code
print("Could not connect to database services after several retries.")
sys.exit(1)
