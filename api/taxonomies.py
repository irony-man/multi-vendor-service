from django.db.models import TextChoices


class VendorType(TextChoices):
    SYNC = "SYNC", "Sync"
    ASYNC = "ASYNC", "Async"
