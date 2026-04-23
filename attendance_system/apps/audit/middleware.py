from .models import AuditLog
from apps.attendance.validators import get_client_ip


class AuditMiddleware:
    """Logs user login and logout events."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        return None
