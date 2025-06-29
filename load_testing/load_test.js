import http from 'k6/http';
import { check, sleep, group } from 'k6';

// --- Configuration ---
const BASE_URL = 'http://localhost:8000';

export const options = {
  stages: [
    { duration: '30s', target: 100 }, // Ramp up to 100 users over 30 seconds
    { duration: '1m', target: 200 }, // Ramp up to 200 users over 1 minute
    { duration: '30s', target: 200 }, // Stay at 200 users for 30 seconds
    { duration: '30s', target: 0 },   // Ramp down to 0 users
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'], // < 1% errors
    'http_req_duration{group:::Submit Job}': ['p(95)<500'], // 95% of POST requests should be below 500ms
    'http_req_duration{group:::Check Status}': ['p(95)<800'], // 95% of GET requests should be below 800ms
  },
};

// --- Main Test Function ---
export default function () {
  let requestId = null;

  // Group 1: Submit a new job
  group('Submit Job', function () {
    const url = `${BASE_URL}/jobs`;
    const payload = JSON.stringify({
      user_id: `user_${__VU}`, // Virtual User ID
      data: {
        info: 'some important data for load testing',
        timestamp: new Date().toISOString(),
      },
    });
    const params = {
      headers: { 'Content-Type': 'application/json' },
    };

    const res = http.post(url, payload, params);

    check(res, {
      'POST /jobs responded with 202': (r) => r.status === 202,
    });

    if (res.status === 202 && res.json('request_id')) {
      requestId = res.json('request_id');
    }
  });

  // Only proceed to check status if we successfully submitted a job
  if (requestId) {
    // Wait for a short time to simulate processing delay
    sleep(2);

    // Group 2: Check the status of the created job
    group('Check Status', function () {
      const url = `${BASE_URL}/jobs/${requestId}`;
      const res = http.get(url);

      check(res, {
        'GET /jobs/{id} responded with 200': (r) => r.status === 200,
        'GET /jobs/{id} has a valid status': (r) => r.json('status') !== undefined,
      });
    });
  }

  // A final sleep to pace the iterations
  sleep(1);
}
