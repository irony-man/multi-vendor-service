# Multi-Vendor Data Fetch Service

This project is a robust, asynchronous data processing service designed to handle requests for multiple external data vendors. It abstracts away vendor-specific complexities like rate limiting and synchronous/asynchronous response patterns into a clean internal API.

### Key Features
* **Asynchronous Processing:** Immediately accepts jobs and processes them in the background using Redis Streams.
* **Resilient and Scalable:** Containerized with Docker and designed with horizontally scalable workers.
* **Safe Rate-Limiting:** A centralized, Redis-based token bucket implementation prevents breaking vendor rate limits.
* **Dependency Healthchecks:** Uses Docker's native healthchecks to ensure services start in the correct order and are ready before accepting work.

---

### Tech Stack
* **Backend:** Django, Gunicorn
* **Queue:** Redis Streams
* **Database:** MongoDB
* **Containerization:** Docker, Docker Compose
* **Vendor Mocks:** FastAPI
* **Load Testing:** k6

---

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
