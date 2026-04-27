from django.urls import path
from .web_views import presenca_scanner, presenca_scan, registrar_presenca_ajax

urlpatterns = [
    path('', presenca_scanner, name='presenca_scanner'),
    path('registrar/', presenca_scan, name='presenca_scan'),
    path('registrar-ajax/', registrar_presenca_ajax, name='registrar_presenca_ajax'),
]