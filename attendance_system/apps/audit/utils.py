from .models import AuditLog
from apps.attendance.validators import get_client_ip


def log_action(user, acao, detalhe='', request=None):
    """Helper to create an audit log entry."""
    ip = None
    ua = ''
    if request:
        ip = get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]
    AuditLog.objects.create(
        usuario=user if user and user.is_authenticated else None,
        acao=acao,
        detalhe=detalhe,
        ip=ip,
        user_agent=ua,
    )
