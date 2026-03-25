from django.utils import timezone


def get_current_datetime():
    return timezone.now()


def generate_reference(prefix):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"
