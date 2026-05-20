import threading
from .models import AuditLog
from apps.attendance.validators import get_client_ip

# Thread-local storage para capturar o request atual dentro dos signals
_thread_locals = threading.local()


def get_current_request():
    """Retorna o request HTTP atual do thread corrente (ou None)."""
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """Retorna o usuário autenticado do request atual (ou None)."""
    request = get_current_request()
    if request is None:
        return None
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    return user


class AuditMiddleware:
    """
    Armazena o request HTTP no thread-local a cada requisição,
    permitindo que os Django signals acessem o usuário e o IP
    sem receber o request como parâmetro.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)
        # Limpa após a resposta para evitar vazamento entre requests
        _thread_locals.request = None
        return response
