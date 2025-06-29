# Multi-Vendor Data Fetch Service

This project is a robust, asynchronous data processing service designed to handle requests for multiple external data vendors. It abstracts away vendor-specific complexities like rate limiting and synchronous/asynchronous response patterns into a clean internal API.
### Tiny Architecture Diagram
```
                  +-------------------------+
                  |         Client          |
                  | (e.g., k6, Postman)     |
                  +-------------------------+
                           |
                           | HTTP POST /jobs
                           | HTTP GET /jobs/{id}
                           v
+-------------------------------------------------------------------------------+
| Docker Network                                                                |
|   +----------------------+      +------------------+                          |
|   |   API Service        |<---->|   Redis Queue    |<---+                     |
|   |   (Django/Gunicorn)  |      |  (Redis Streams) |    | Read Job            |
|   +---------+------------+      +------------------+    |                     |
|             | read/write                                |                     |
|             v                        +------------------+                     |
|   +----------------------+           | Background Worker|                     |
|   |      Database        |           |  (Python Script) |                     |
|   |     (MongoDB)        |<----------+----+-------------+                     |
|   +----------------------+                | Call Vendor (respects rate limit) |
|             ^                             v                                   |
|             | POST Webhook      +-----------------------+                     |
|             +-------------------+ Mock Vendor Service   |                     |
|                                 | (FastAPI)             |                     |
|                                 +-----------------------+                     |
+-------------------------------------------------------------------------------+
```

### Quick Start

**Prerequisites:** Docker & Docker Compose, k6 (optional, for testing).

1.  **Clone the repository and configure the environment:**
    ```
    git clone <your-repo-url>
    cd multi-vendor-service
    cp .env.example .env
    ```
2. **Build and run all services:**
    ```
    docker compose up --build -d
    ```
3. **Check service status:**
    ```
    docker compose ps
    ```

### API Usage
1.  **Submit a Job**
    * **Endpoint:** `POST /jobs`
    * **Description:** Queues a job for processing and responds instantly.
    * **cURL Example:**
        ```
        curl --location 'http://localhost:8000/jobs' \
        --header 'Content-Type: application/json' \
        --data '{
            "payload": {
                "customer_id": 12345,
                "options": {
                    "priority": "high",
                    "verify_address": true
                }
            },
            "vendor": "sync" or "async"
        }'
        ```
    * **Response:**
        ```
        {
            "request_id": "a-unique-uuid-string"
        }
        ```
2. **Check Job Status**

    * **Endpoint:** `GET /jobs/{request_id}`
    * **Description:** Retrieves the status of a previously submitted job.
    * **cURL Example:**
        ```
        REQUEST_ID="your-request-id"
        curl --location "http://localhost:8000/jobs/$REQUEST_ID"
        ```

    * **Response:**
        ```
        {
            "request_id": "your-request-id",
            "status": "complete",
            "result": { ... }
        }
        ```
### Key Design Decisions & Trade-offs
* **Queueing (Redis Streams):**

    * **Decision:** Used Redis Streams for the job queue.

    * **Reasoning:** It's lightweight, persistent, and has native support for consumer groups, which provides resilient, scalable workers out-of-the-box. This is a simpler alternative to RabbitMQ or Kafka for this project's scale.

    * **Trade-off:** Lacks the advanced routing capabilities of RabbitMQ or the massive-scale log guarantees of Kafka, which were not required here.

* **Service Readiness (Docker Healthchecks):**

    * **Decision:** Used Docker Compose's built-in `healthcheck` feature to manage startup dependencies.

    * **Reasoning:** This is more robust than a simple `depends_on`, as it actively polls services (e.g., the mock vendor) to ensure they are truly ready to accept traffic before dependent services (like the worker) start. This prevents common race conditions and DNS resolution errors.

    * **Trade-off:** Adds a small amount of configuration complexity to `docker-compose.yml` but greatly increases startup reliability.

* **Rate Limiting (Redis `SETNX`):**

    * **Decision:** Implemented a Token Bucket algorithm using Redis's atomic `SET NX EX` command.

    * **Reasoning:** This provides a centralized and highly efficient lock that functions correctly across multiple, distributed worker instances without needing complex application-level locking logic.

    * **Trade-off:** Tightly couples the rate-limiting logic to Redis, but this is an acceptable trade-off since Redis is already a core dependency.

* **Database Interaction (`pymongo` vs. ORM):**

    * **Decision:** Used the `pymongo` library for direct interaction with MongoDB, bypassing the Django ORM.

    * **Reasoning:** This decouples the core data logic from the Django framework, simplifies the worker (which doesn't need to be a full Django app), and is generally more performant for simple document storage.

    * **Trade-off:** We lose the convenience of the Django Admin interface for directly viewing and managing jobs, which is an acceptable loss for a backend service like this.
