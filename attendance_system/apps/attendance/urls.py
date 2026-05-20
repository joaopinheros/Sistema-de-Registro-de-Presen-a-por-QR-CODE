from django.urls import path
from .web_views import (
    presenca_scanner,
    presenca_scan,
    registrar_presenca_ajax,
    registrar_presenca_async,
    presenca_task_status,
)

urlpatterns = [
    path('', presenca_scanner, name='presenca_scanner'),
    path('registrar/', presenca_scan, name='presenca_scan'),
    path('registrar-ajax/', registrar_presenca_ajax, name='registrar_presenca_ajax'),
    # Endpoints assíncronos via Celery + RabbitMQ
    path('registrar-async/', registrar_presenca_async, name='registrar_presenca_async'),
    path('status/<str:task_id>/', presenca_task_status, name='presenca_task_status'),
]