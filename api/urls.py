from django.urls import path

from api.views import JobStatusView, JobSubmissionView, VendorWebhookView

urlpatterns = [
    path("jobs", JobSubmissionView.as_view(), name="submit-job"),
    path(
        "jobs/<str:request_id>",
        JobStatusView.as_view(),
        name="get-job-status",
    ),
    path(
        "vendor-webhook/<str:vendor>",
        VendorWebhookView.as_view(),
        name="vendor-webhook",
    ),
]
